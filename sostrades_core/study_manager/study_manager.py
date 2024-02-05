'''
Copyright 2022 Airbus SAS
Modifications on 2023/06/20-2023/11/03 Copyright 2023 Capgemini

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
from sostrades_core.study_manager.base_study_manager import BaseStudyManager
from sostrades_core.sos_processes.script_test_all_usecases import processed_test_one_usecase
from os.path import abspath, basename, dirname, relpath, splitext, join, exists
from os import sep
import numpy as np


class StudyManager(BaseStudyManager):

    def __init__(self, process_module_name:str, study_name, run_usecase=True, execution_engine=None):
        """
        Constructor

        :params: process_module_name, module name of the process, ex : sostrades_core.sos_processes.test.process
        :type: str

        :params: study_name, Name of the study
        :type: str
        """
        # init dspace dict
        self.dspace = {}
        self.dspace['dspace_size'] = 0

        process_module_name_split = process_module_name.split(".")

        super().__init__(
            repository_name=".".join(process_module_name_split[:-1]),
            process_name=process_module_name_split[-1],
            study_name=study_name,
            run_usecase=run_usecase,
            execution_engine=execution_engine)

    def update_dspace_with(self, name, value, lower, upper):
        ''' type(value) has to be ndarray
        '''
        if not isinstance(lower, (list, np.ndarray)):
            lower = [lower] * len(value)
        if not isinstance(upper, (list, np.ndarray)):
            upper = [upper] * len(value)
        self.dspace['variable'].append(name)
        self.dspace['value'].append(value)
        self.dspace['lower_bnd'].append(lower)
        self.dspace['upper_bnd'].append(upper)
        self.dspace['dspace_size'] += len(value)

    def update_dspace_dict_with(self, name, value, lower, upper, activated_elem=None, enable_variable=True):
        if not isinstance(lower, (list, np.ndarray)):
            lower = [lower] * len(value)
        if not isinstance(upper, (list, np.ndarray)):
            upper = [upper] * len(value)

        if activated_elem is None:
            activated_elem = [True] * len(value)
#         # TODO: to remove once lists are converted in SoSTrades
#         if not isinstance(value, ndarray):
#             if isinstance(value, list):
#                 value = array(value)
#                 ini_type = "list"
#             elif isinstance(value, float):
#                 value = array([value])
#                 ini_type = "float"
#             else:
#                 raise ValueError(f"Design variable {name} is not an numpy array but of type <{ini_type}>.")
#             msg = f"StudyManager: Design variable {name} type is <{ini_type}> (unsupported for now) "
#             msg += "and has been converted to <ndarray>."
#             self.execution_engine.logger.info(msg)

        #
        self.dspace[name] = {'value': value,
                             'lower_bnd': lower, 'upper_bnd': upper, 'enable_variable': enable_variable, 'activated_elem': activated_elem}

        self.dspace['dspace_size'] += len(value)

    def merge_design_spaces(self, dspace_list):
        """
        Merge design spaces
        """
        for dspace in dspace_list:
            dspace_size = dspace.pop('dspace_size')
            self.dspace['dspace_size'] += dspace_size
            self.dspace.update(dspace)

    def setup_usecase_sub_study_list(self, merge_design_spaces=False):
        """
        Instantiate sub studies and values dict from setup_usecase
        """
        values_dict_list = []
        instanced_sub_studies = []
        for sub_study in self.sub_study_list:
            instance_sub_study = sub_study(
                self.year_start, self.year_end, self.time_step)
            instance_sub_study.study_name = self.study_name
            data_dict = instance_sub_study.setup_usecase()
            values_dict_list.extend(data_dict)
            instanced_sub_studies.append(instance_sub_study)

        if merge_design_spaces:
            self.merge_design_spaces(
                [sub_study.dspace for sub_study in instanced_sub_studies])

        return values_dict_list, instanced_sub_studies

    def set_debug_mode(self):
        self.execution_engine.set_debug_mode()

    def get_dv_arrays(self):
        """
        Method to get dv_arrays
        """
        pass

    def test(self, force_run: bool = False):
        test_passed, error_msg = processed_test_one_usecase(usecase=self.study_full_path, force_run=force_run)
        if not test_passed:
            raise Exception(f"Test not passed {error_msg}")
        else:
            print('Test is OK')
