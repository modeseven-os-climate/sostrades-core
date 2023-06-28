"""
Copyright 2022 Airbus SAS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from typing import Union, Optional

from sostrades_core.tools.post_processing.post_processing_factory import PostProcessingFactory

"""
mode: python; py-indent-offset: 4; tab-width: 8; coding:utf-8
"""

from sostrades_core.study_manager.base_study_manager import BaseStudyManager
from sostrades_core.sos_processes.processes_factory import SoSProcessFactory
from importlib import import_module
from os.path import dirname, isdir
from os import listdir, makedirs, environ
import logging

from copy import deepcopy
from tempfile import gettempdir
import traceback
from gemseo.utils.compare_data_manager_tooling import compare_dict, \
    delete_keys_from_dict
from multiprocessing import Process, Queue
from queue import Empty
import time

PROCESS_IN_PARALLEL = 5


def manage_process_queue(process_list, message_queue):
    """ Regarding a given process list (already start)
    manage sub process lifecycle and queue message passing

    :params: process_list, list of processses to manage
    :type: multiprocessing.Process

    :params: message_queue, message queue associted to process and subprocesses
    :type: multiprocessing.Queue


    :return: [str, str], [test status, error message list]
    """
    liveprocs = list(process_list)
    global_output_error = ''
    global_test_passed = True
    while liveprocs:
        try:
            while 1:
                messages = message_queue.get(False)
                test_passed = messages[0]
                output_error = messages[1]

                if not test_passed:
                    global_test_passed = False

                if len(output_error) > 0:
                    global_output_error += output_error
        except Empty:
            pass

        time.sleep(0.5)  # Give tasks a chance to put more data in
        if not message_queue.empty():
            continue
        liveprocs = [p for p in liveprocs if p.is_alive()]

    return global_test_passed, global_output_error


def manage_process_launch(process_list, message_queue) -> tuple[str, str]:
    """ Regarding a given process list (not started)
    manage sub process launching

    :params: process_list, list of processses to manage
    :type: multiprocessing.Process

    :params: message_queue, message queue associted to process and subprocesses
    :type: multiprocessing.Queue


    :return: (str, str) , test status and error message list
    """

    global_output_error = ''
    global_test_passed = True

    while len(process_list) > 0:
        candidate_process = []

        if len(process_list) > PROCESS_IN_PARALLEL:
            candidate_process = [process_list.pop()
                                 for index in range(PROCESS_IN_PARALLEL)]
        else:
            candidate_process = process_list
            process_list = []

        for process in candidate_process:
            process.start()

        result_test_passed, result_output_error = manage_process_queue(
            candidate_process, message_queue)

        global_test_passed = global_test_passed and result_test_passed

        if len(result_output_error) > 0:
            global_output_error += result_output_error

    return global_test_passed, global_output_error


def test_all_usecases(processes_repo: str, force_run=False):
    """
    Test all usecases in a repo.
    Each usecase is tested in a process.
    """
    usecases = get_all_usecases(processes_repo)
    message_queue = Queue()
    process_list = []

    for usecase in usecases:
        process_list.append(
            Process(target=processed_test_one_usecase, args=(usecase, message_queue, force_run,)))

    return manage_process_launch(process_list, message_queue)


def get_all_usecases(processes_repo: str) -> list[str]:
    """
    Retrieve all usecases in a repository
    :params: processes_repo, repository where to find processes
    """

    process_factory = SoSProcessFactory(additional_repository_list=[
        processes_repo], search_python_path=False)
    process_list = process_factory.get_processes_dict()
    usecase_list = []
    for repository in process_list:
        for process in process_list[repository]:
            try:
                process_module = '.'.join([repository, process])
                imported_module = import_module(process_module)
                if imported_module is not None and imported_module.__file__ is not None:
                    process_directory = dirname(imported_module.__file__)
                    # Run all usecases
                    for usecase_py in listdir(process_directory):
                        if usecase_py.startswith('usecase'):
                            usecase = usecase_py.replace('.py', '')
                            usecase_list.append('.'.join([repository, process, usecase]))
            except Exception as error:
                logging.error(f'An error occurs when trying to load {process_module}\n{error}')
    return usecase_list


def multiple_run(usecase, force_run=False) -> tuple[Union[BaseStudyManager, None],
                                                    Union[BaseStudyManager, None],
                                                    Union[dict, None],
                                                    Union[dict, None]]:
    """
        Run twice a usecase and return the two treeviews from the runs
        :params: usecase, usecase to run twice
        :type: String
        :returns: Two treeview as dictionary
    """
    print(f'----- RUN TWICE A USECASE {usecase} -----')
    # Instanciate Study
    imported_module = import_module(usecase)
    uc = getattr(imported_module, 'Study')()

    # ----------------------------------------------------
    # First step : Dump data to a temp folder

    # Dump data can be set using en environment variable (mainly for devops test purpose
    # So check that environment variable before using de default location

    # Default variable location
    base_dir = f'{gettempdir()}/references'

    if environ.get('SOS_TRADES_REFERENCES_SPECIFIC_FOLDER') is not None:
        base_dir = environ['SOS_TRADES_REFERENCES_SPECIFIC_FOLDER']

    if not isdir(base_dir):
        makedirs(base_dir, exist_ok=True)

    logging.info(f'Reference location for use case {usecase} is {base_dir}')

    uc.set_dump_directory(base_dir)
    uc.load_data()
    dump_dir = uc.dump_directory
    uc.dump_data(dump_dir)
    uc.dump_disciplines_data(dump_dir)
    study_1, study_2, dm_1, dm_2 = None, None, None, None

    if uc.run_usecase or force_run:
        # Set repo_name, proc_name, study_name to create BaseStudyManager
        repo_name = uc.repository_name
        proc_name = uc.process_name
        study_name = uc.study_name

        logging.info("---- FIRST RUN ----")
        # First run : Load Data in a new BaseStudyManager and run study
        try:
            study_1 = BaseStudyManager(repo_name, proc_name, study_name)
            study_1.load_data(from_path=dump_dir)
            study_1.set_dump_directory(base_dir)
            study_1.run(logger_level=logging.DEBUG, dump_study=True, for_test=True)
            # Deepcopy dm
            dm_1 = deepcopy(
                study_1.execution_engine.get_anonimated_data_dict())
            study_1.dump_data(dump_dir)
        except Exception as e:
            raise Exception(f'Error during first run: {e}')

        # Second run : Load Data in a new BaseStudyManager and run study
        logging.info("---- SECOND RUN ----")
        try:
            study_2 = BaseStudyManager(repo_name, proc_name, study_name)
            study_2.load_data(from_path=dump_dir)
            study_2.run(logger_level=logging.DEBUG)
            # Deepcopy dm
            dm_2 = deepcopy(
                study_2.execution_engine.get_anonimated_data_dict())
        except Exception as e:
            raise Exception(f'Error during second run: {e}')

        # Delete ns ref from the two DMs
        delete_keys_from_dict(dm_1), delete_keys_from_dict(dm_2)
    else:
        logging.info(f'{usecase} is configured not to run, skipping double run.')

    return study_1, study_2, dm_1, dm_2


def multiple_configure(usecase):
    """
        Configure twice a usecase and return the two treeviews from the configure
        :params: usecase, usecase to configure twice
        :type: String
        :returns: Two dm as dictionary
    """

    logging.info(f'----- CONFIGURE TWICE A USECASE {usecase} -----')
    # Instanciate Study
    imported_module = import_module(usecase)
    uc = getattr(imported_module, 'Study')()
    # First step : Dump data to a temp folder
    uc.set_dump_directory(gettempdir())
    uc.load_data()
    dump_dir = uc.dump_directory
    uc.dump_data(dump_dir)

    logging.info("---- FIRST CONFIGURE ----")
    # First run : Load Data in a new BaseStudyManager and run study
    study_1 = BaseStudyManager(repository_name=uc.repository_name, process_name=uc.process_name, study_name=uc.study_name)
    study_1.load_data(from_path=dump_dir)
    study_1.execution_engine.configure()
    # Deepcopy dm
    dm_dict_1 = deepcopy(study_1.execution_engine.get_anonimated_data_dict())
    study_1.dump_data(dump_dir)

    # Second run : Load Data in a new BaseStudyManager and run study
    logging.info("---- SECOND CONFIGURE ----")
    study_2 = BaseStudyManager(repository_name=uc.repository_name, process_name=uc.process_name, study_name=uc.study_name)
    study_2.load_data(from_path=dump_dir)
    study_2.execution_engine.configure()
    # Deepcopy dm
    dm_dict_2 = deepcopy(study_2.execution_engine.get_anonimated_data_dict())
    study_2.set_dump_directory(dump_dir=dump_dir)

    delete_keys_from_dict(dm_dict_1), delete_keys_from_dict(dm_dict_2)

    return study_1, study_2, dm_dict_1, dm_dict_2,


def test_compare_dm(dm_1: dict, dm_2: dict, usecase: str, msg: str) -> tuple[bool, str]:
    """
    Compares dm from two configured studies.
    Returns:
         compare_test_passed: bool, dms are identical,
         error_msg_compare: error message, (empty string if test is passed)
    """
    compare_test_passed = True
    error_msg_compare = ''
    try:
        dict_error = {}
        compare_dict(dm_1, dm_2, '', dict_error)
        if dict_error != {}:
            compare_test_passed = False
            for error in dict_error:
                error_msg_compare += f'Error while comparing data dict {msg} {usecase}:\n'
                error_msg_compare += f'Mismatch in {error}: {dict_error.get(error)}'
                error_msg_compare += '\n---------------------------------------------------------\n'
    except Exception as e:
        traceback.print_exc()
        compare_test_passed = False
        error_msg_compare += f'Error while comparing data_dicts of {usecase}:\n {e}'
        error_msg_compare += '\n---------------------------------------------------------\n'

    return compare_test_passed, error_msg_compare


def test_double_configuration(usecase: str) -> tuple[Union[BaseStudyManager, None],
                                                     Union[BaseStudyManager, None],
                                                     Union[dict, None],
                                                     Union[dict, None],
                                                     bool, str]:
    """
    Double configuration of a usecase
    Returns:
         compare_test_passed: bool, dms are identical,
         error_msg_compare: error message, (empty string if test is passed)
    """
    double_config_passed = True
    error_msg_compare = ''
    try:
        study_1, study_2, dm_1, dm_2 = multiple_configure(usecase=usecase)
    except Exception as e:
        double_config_passed = False
        error_msg_compare += f'Error while Configuring twice {usecase}:\n {e}'
        error_msg_compare += '\n---------------------------------------------------------\n'
        study_1, study_2, dm_1, dm_2 = None, None, None, None
        return study_1, study_2, dm_1, dm_2, double_config_passed, error_msg_compare

    double_config_passed, error_msg_compare = test_compare_dm(dm_1=dm_1, dm_2=dm_2, usecase=usecase,
                                                             msg='following double configuration of')
    return study_1, study_2, dm_1, dm_2, double_config_passed, error_msg_compare


def test_data_integrity(study: BaseStudyManager) -> tuple[bool, str]:
    """
    Double configuration of a usecase
    Returns:
         compare_test_passed: bool, dms are identical,
         error_msg_compare: error message, (empty string if test is passed)
    """
    data_integrity_passed = True
    error_msg_data_integrity = ''

    data_integrity_msg = study.ee.get_data_integrity_msg()
    if data_integrity_msg != '':
        data_integrity_passed = False
        error_msg_data_integrity += f'Error while testing data integrity for usecase {study.study_full_path}:' \
                                    f'\n {data_integrity_msg}'
        error_msg_data_integrity += '\n---------------------------------------------------------\n'

    return data_integrity_passed, error_msg_data_integrity


def test_double_run(study: BaseStudyManager, force_run: bool=False) -> tuple[bool, str]:
    """
    Test double run of a study

    - run study given in input
    - dump it
    - load it in a study2
    - run study2
    - compare dm of study and study2

    test is passed if dms are equal for both studies
    """
    error_msg_run = ''
    run_test_passed = True

    if not(study.run_usecase or force_run):
        logging.info(f'{study.study_full_path} is configured not to run, skipping double run.')
        return run_test_passed, error_msg_run
    logging.info("---- FIRST RUN ----")
    # First run : Load Data in a new BaseStudyManager and run study
    try:
        # study.load_data(from_path=dump_dir) # already done in multiple_configure i think
        study.run(logger_level=logging.DEBUG, dump_study=True, for_test=True)
        # Deepcopy dm
        dm_1 = deepcopy(
            study.execution_engine.get_anonimated_data_dict())
        study.dump_data()
    except Exception as e:
        raise Exception(f'Error during first run: {e}')

    # Second run : Load Data in a new BaseStudyManager and run study
    logging.info("---- SECOND RUN ----")
    try:
        study_2 = BaseStudyManager(repository_name=study.repository_name,
                                   process_name=study.process_name,
                                   study_name=study.study_name)
        study_2.load_data(from_path=study.dump_directory)
        study_2.run(logger_level=logging.DEBUG)
        # Deepcopy dm
        dm_2 = deepcopy(
            study_2.execution_engine.get_anonimated_data_dict())
    except Exception as e:
        raise Exception(f'Error during second run: {e}')

    def clean_keys(data_dict: dict):
        """Clean keys in dictionnary for comparison"""
        delete_keys_from_dict(data_dict)
        unwanted_keys, keys_to_none = [], {}
        for key, value in data_dict.items():
            if 'residuals_history' in key:
                unwanted_keys += [key]
            if isinstance(value, dict):
                if 'type_metadata' in value.keys():
                    keys_to_none[key] = 'type_metadata'
        for key, value in keys_to_none.items():
            data_dict[key][value] = None
        for key in unwanted_keys:
            data_dict.pop(key)

    clean_keys(dm_1); clean_keys(dm_2)

    run_test_passed, error_msg_run = test_compare_dm(dm_1=dm_1, dm_2=dm_2, usecase=study_2.study_full_path,
                                                     msg='after double run of')

    return run_test_passed, error_msg_run


def test_post_processing_study(study: BaseStudyManager) -> tuple[bool, str]:
    """This tests evaluates if the data_dict remains the same after computing the post_processings in a usecase"""
    error_msg_post_processing = ''
    post_processing_test_passed = True

    dm_before_pp = deepcopy(study.execution_engine.get_anonimated_data_dict())
    # First run : Load Data in a new BaseStudyManager and run study

    ppf = PostProcessingFactory()
    try:
        for disc in study.execution_engine.root_process.proxy_disciplines:
            filters = ppf.get_post_processing_filters_by_discipline(
                disc)
            graph_list = ppf.get_post_processing_by_discipline(
                disc, filters, as_json=False)
        dm_after_pp = deepcopy(study.execution_engine.get_anonimated_data_dict())
    except Exception as e:
        error_msg_post_processing += f'Error while computing post processing for usecase {study.study_full_path}:\n {e}'
        post_processing_test_passed = False
        return post_processing_test_passed, error_msg_post_processing

    post_processing_test_passed, error_msg_post_processing = test_compare_dm(dm_1=dm_before_pp, dm_2=dm_after_pp,
                                                                             msg='after computing Post Processings',
                                                                             usecase=study.study_name)

    return post_processing_test_passed, error_msg_post_processing


def processed_test_one_usecase(usecase: str, message_queue: Optional[Queue] = None, force_run: bool = False) -> tuple[bool, str]:
    """
    Tests a usecase
    - test double configuration
    - test data integrity
    - if not MDO : test integrity of data after computing post-processings
    - if not MDO and not MDA : test double run

    """
    logging.disable(logging.INFO)

    study_1, study_2, dm_1, dm_2, double_configuration_passed, error_msg_double_config = test_double_configuration(
        usecase=usecase)
    error_msg = error_msg_double_config
    test_passed = double_configuration_passed

    if double_configuration_passed:
        data_integrity_passed, error_msg_data_integrity = test_data_integrity(study=study_2)
        error_msg += error_msg_data_integrity
        test_passed = data_integrity_passed

        if data_integrity_passed and not study_2.ee.factory.contains_mdo:
            post_processing_passed, error_msg_post_processing = test_post_processing_study(
                study=study_2)
            test_passed = post_processing_passed
            error_msg += error_msg_post_processing

            if post_processing_passed and not study_2.ee.factory.contains_mda_with_strong_couplings:
                run_test_passed, error_msg_run = test_double_run(study=study_2, force_run=force_run)
                test_passed = run_test_passed
                error_msg += error_msg_run

    if message_queue is not None:
        message_queue.put([test_passed, error_msg])
    return test_passed, error_msg
