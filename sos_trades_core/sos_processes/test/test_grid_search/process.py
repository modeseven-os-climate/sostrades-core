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
    def get_builders(self):

        mod1_path = 'sos_trades_core.sos_wrapping.test_discs.disc1_all_types.Disc1'
        grid_search = 'GridSearch'

        disc1_builder = self.ee.factory.get_builder_from_module(
            'Disc1', mod1_path)

        sa_builder = self.ee.factory.create_evaluator_builder(
            grid_search, 'grid_search', disc1_builder)

        return sa_builder