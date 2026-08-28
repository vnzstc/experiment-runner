from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from os.path import dirname, realpath, basename

import configparser
import os
import subprocess
import shlex
import time
import uuid
import csv

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    # ================================ USER SPECIFIC CONFIG ================================
    name:                       str             = "npm-exp"
    results_output_path:        Path            = ROOT_DIR / 'results'
    operation_type:             OperationType   = OperationType.AUTO
    time_between_runs_in_ms:    int             = 1000 # cool down between runs
    rapl_overflow_value                         = 262143.328850

    # ================================ SSH CONNECTION SETTINGS ================================
    _conf_path = ROOT_DIR / 'connection.ini'
    _conf = configparser.ConfigParser()
    if _conf_path.exists():
        _conf.read(_conf_path)
    else:
        raise FileNotFoundError(
            f"Missing {_conf_path}."
        )
    _ssh = _conf["ssh"]

    jump_host:                  str             = _ssh.get("jump_host")
    jump_port:                  int             = _ssh.getint("jump_port", fallback=22)
    jump_user:                  str             = _ssh.get("jump_user")
    target_host:                str             = _ssh.get("target_host")
    target_port:                int             = _ssh.getint("target_port", fallback=22)
    target_user:                str             = _ssh.get("target_user")
    ssh_key_path:               Optional[str]  = _ssh.get("ssh_key_path", fallback=None) or None

    # ================================ Runner Core Logic ================================
    def __init__(self):
        """Executes immediately after program start, on config load"""
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN       , self.before_run       ),
            (RunnerEvents.START_RUN        , self.start_run        ),
            #(RunnerEvents.START_MEASUREMENT, self.start_measurement),
            #(RunnerEvents.INTERACT         , self.interact         ),
            #(RunnerEvents.STOP_MEASUREMENT , self.stop_measurement ),
            (RunnerEvents.STOP_RUN         , self.stop_run         ),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT , self.after_experiment )
        ])

        self.run_table_model = None  # Initialized later
        # ================================ CONNECTION STRINGS ================================
        self.jump_address = f"{self.jump_user}@{self.jump_host}:{self.jump_port}"
        self.target_address = f"{self.target_user}@{self.target_host}"
        self.proc = None
        # ================================ SERVER PATHS ================================
        self.target_exp_dir = 'npm-exp'
        self.target_res_dir = f'{self.target_exp_dir}/results'
        self.target_pkg_dir = f'{self.target_exp_dir}/pkgs'
        self.cmds = {
            'npm' : 'tar -xzf',
            'xz' : 'xz -d'
        }
        self.target_run_dir = ''

        output.console_log("Custom config loaded")

    def _list_remote_subjects(self, alg_key: str) -> list[str]:
        remote_path = f'{self.target_pkg_dir}/{alg_key}'
        jump_address = f"{self.jump_user}@{self.jump_host}:{self.jump_port}"
        target_address = f"{self.target_user}@{self.target_host}"

        cmd = ['ssh', '-i', self.ssh_key_path,'-J', jump_address, target_address, f'ls -1 {remote_path}']
        out = subprocess.check_output(cmd, text=True)
        return [line for line in out.strip().splitlines() if line]

    def _read_sample(self, alg_key: str) -> list[str]:
        '''Reads a previously retrieved sample of packages.
        The alg_key arg indicates the compression algorithm to consider.
        '''
        path = Path(f'npm-exp/pkgs/samples/{alg_key}.csv')
        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return [row['name'] for row in reader]

    #def _read_sample(self, alg_key: str) -> list[str]:
    #    path = Path(f'samples/{alg_key}.csv')
    #    sample = pd.read_csv(path)
    #    return sample['name'].astype(str).to_list()

    def create_run_table_model(self) -> RunTableModel:
        # subjects_per_alg = {a: self._list_remote_subjects(a) for a in self.cmds.keys()}
        subjects_per_alg = {a: self._read_sample(a) for a in self.cmds.keys()} 

        alg = FactorModel(
            "alg", self.cmds.keys()
        )

        all_subjects = sorted(set().union(*subjects_per_alg.values()))
        subjects = FactorModel("subject", all_subjects)

        include_rows_spec = []
        for alg_name, subject_list in subjects_per_alg.items():
            include_rows_spec.append({
                alg: [alg_name],
                subjects: subject_list
            })

        self.run_table_model = RunTableModel(
            factors=[alg, subjects],
            include_rows=include_rows_spec,
            shuffle=True,
            data_columns=['avg_energy']
        )

        return self.run_table_model

    def _drain_startup_banner(self):
        marker = f"__READY_{uuid.uuid4().hex}__"
        self.proc.stdin.write(f"echo {marker}\n")
        self.proc.stdin.flush()
        for line in self.proc.stdout:
            if marker in line:
                break

    def before_experiment(self) -> None:
        jump_address = f"{self.jump_user}@{self.jump_host}:{self.jump_port}"
        target_address = f"{self.target_user}@{self.target_host}"

        self.proc = subprocess.Popen(
            ['ssh', '-i', self.ssh_key_path,'-J', jump_address, target_address],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        self._drain_startup_banner()

        # Create Results DIR on the Server
        self.proc.stdin.write(
            f"rm -rf {self.target_res_dir}; mkdir {self.target_res_dir}\n"
        )
        self.proc.stdin.flush()
        output.console_log("Before Experiment")

    def before_run(self) -> None:
        # @TODO: I would have liked to have the context here too.
        output.console_log("Config.before_run() called!")

    def start_run(self, context: RunnerContext) -> None:
        #for d in self.run_table_model.experiment_run_table:
        #    print(basename(context.run_dir))
        #    print(d['__run_id'])
        #    if d['__run_id'] == basename(context.run_dir):
        #        print(d)
        #        print('found')
        #        break
        #print('not_found')
        # Create run result dir on the server
        self.target_run_dir = f'{self.target_res_dir}/{basename(context.run_dir)}'
        subject = next(
            d['subject'] for d in self.run_table_model.experiment_run_table if d['__run_id'] == basename(context.run_dir)
        )

        key, pkg = Path(subject).parts
        cmd_output = f'{self.target_run_dir}/decompressed/'
        cmd = f'{self.cmds[key]} npm-exp/pkgs/{subject} -C {cmd_output}' 
        # create run directory on the server
        self.proc.stdin.write(f"mkdir {self.target_run_dir}\n")
        self.proc.stdin.flush()
        # create dir to store the output of the decompression
        self.proc.stdin.write(f"mkdir {cmd_output}\n") 
        self.proc.stdin.flush()
        # self.proc.stdin.write(f'sudo npm-exp/profile.sh {self.target_run_dir} sleep 2' + f'; echo __END__\n') 
        self.proc.stdin.write(f'sudo npm-exp/profile.sh {self.target_run_dir} {cmd}' + f'; echo __END__\n')
        self.proc.stdin.flush()
        res = []
        for line in self.proc.stdout:
            if '__END__' in line:
                break
            res.append(line)
        output.console_log(res)

    #def start_measurement(self, context: RunnerContext) -> None:
    #    output.console_log(f"Measurement started")

    #def interact(self, context: RunnerContext) -> None:
    #    output.console_log("Config.interact() called!")

    #def stop_measurement(self, context: RunnerContext) -> None:
    #    output.console_log("Config.stop_measurement() called!")

    def stop_run(self, context: RunnerContext) -> None:
        local_path = f'{context.run_dir}/power.csv'
        remote_path = f'{self.target_res_dir}/{basename(context.run_dir)}/power.csv'

        cp_cmd = [
            'scp', '-i', self.ssh_key_path, '-O', '-J', self.jump_address, f'{self.target_user}@{self.target_host}:{remote_path}', local_path
        ]
        subprocess.run(cp_cmd, check=True)
        output.console_log("Config.stop_run() called!")

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        output.console_log("Config.populate_run_data() called!")
        return None

    # This is where we close the SSH connection opened in before_experiment.
    def after_experiment(self) -> None:
        self.proc.stdin.write('exit\n')
        self.proc.stdin.flush()
        self.proc.stdin.close()
        self.proc.wait()
        output.console_log("SSH Connection Closed")

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
