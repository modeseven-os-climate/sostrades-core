'''
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
'''
# mode: python; py-indent-offset: 4; tab-width: 8; coding:utf-8
#-- Generate test 1 process
from sos_trades_core.sos_processes.base_process_builder import BaseProcessBuilder

class ProcessBuilder(BaseProcessBuilder):

    # ontology information
    _ontology_data = {
        'label': 'Process DoE_Eval of a Hessian Discipline from a processus of the discipline',
        'description': 'Process to Instantiate the DoE_Eval of a Hessian Discipline build directly from a processus for discipline creation',
        'category': '',
        'version': '',
    }
    def get_builders(self):
        repo = 'sos_trades_core.sos_processes.test'
        builder_list = self.ee.factory.get_builder_from_process(
                                             repo=repo,mod_id='test_disc_hessian')
        self.ee.ns_manager.add_ns('ns_doe_eval', f'{self.ee.study_name}.DoE_Eval')
        doe_eval_builder = self.ee.factory.create_evaluator_builder(
                                             'DoE_Eval', 'build_doe_eval', builder_list)
        return doe_eval_builder
