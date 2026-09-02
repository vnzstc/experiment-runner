import itertools
import random
from typing import Dict, List, Tuple

from ConfigValidator.CustomErrors.BaseError import BaseError
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.RunTable.Models.RunProgress import RunProgress
from ConfigValidator.Config.Models.FactorModel import FactorModel


class RunTableModel:
    def __init__(self,
                 factors: List[FactorModel],
                 exclude_combinations: List[Dict[FactorModel, List[SupportsStr]]] = None,
                 include_rows: List[Dict[FactorModel, List[SupportsStr]]] = None,
                 repetitions: int = 1,
                 data_columns: List[str] = None,
                 shuffle: bool = False
                 ):

        if exclude_combinations is None:
            exclude_combinations = {}

        if include_rows is None:
            include_rows = []

        if data_columns is None:
            data_columns = []

        if repetitions < 1:
            raise BaseError("Negative number of repetitions detected!")

        if len(set([factor.factor_name for factor in factors])) != len(factors):
            raise BaseError("Duplicate factor name detected!")

        if len(set(data_columns)) != len(data_columns):
            raise BaseError("Duplicate data column detected!")

        self.__factors = factors
        self.__exclude_combinations = exclude_combinations
        self.__include_rows = include_rows
        self.__repetitions = repetitions
        self.__data_columns = data_columns
        self.__shuffle = shuffle
        self.__experiment_run_table = None

    def get_factors(self) -> List[FactorModel]:
        return self.__factors

    def get_data_columns(self) -> List[str]:
        return self.__data_columns

    def generate_experiment_run_table(self) -> List[Dict]:
        def __filter_list(full_list: List[Tuple]):
            if len(self.__exclude_combinations) == 0:
                return full_list

            to_remove_indices = []
            for exclusion in self.__exclude_combinations:
                list_of_lists = []
                indexes = []
                for factor, treatment_list in exclusion.items():
                    list_of_lists.append(treatment_list)
                    indexes.append(self.__factors.index(factor))
                exclude_combinations_list = list(itertools.product(*list_of_lists))

                for idx, elem in enumerate(full_list):
                    for exclude_combo in exclude_combinations_list:
                        if all([exclude_combo[i] == elem[indexes[i]] for i in range(len(indexes))]):
                            to_remove_indices.append(idx)

            to_remove_indices.sort(reverse=True)
            for idx in to_remove_indices:
                del full_list[idx]
            return full_list

        # Store intermediate rows as dictionaries
        rows: List[Dict[str, SupportsStr]] = []

        if self.__include_rows:
            for spec in self.__include_rows:
                # Get the factors defined in this specification block (e.g., alg, subjects)
                spec_factors = list(spec.keys())
                # Gather their matching value lists
                spec_value_lists = [spec[f] for f in spec_factors]

                # Pair them up properly (e.g. ['node-tar'] x ['pkg1', 'pkg2'])
                for combo in itertools.product(*spec_value_lists):
                    row_dict = {}
                    for factor, value in zip(spec_factors, combo):
                        row_dict[factor.factor_name] = value
                    rows.append(row_dict)

        elif self.__exclude_combinations:
            list_of_lists = [factor.treatments for factor in self.__factors]
            combinations_list = list(itertools.product(*list_of_lists))
            filtered_list = __filter_list(combinations_list)

            # Convert standard tuples into dicts matching factor names
            for combo in filtered_list:
                row_dict = {}
                for factor, value in zip(self.__factors, combo):
                    row_dict[factor.factor_name] = value
                rows.append(row_dict)

        experiment_run_table = []

        for j in range(self.__repetitions):
            for i, base_row in enumerate(rows):
                row_dict = {
                    '__run_id': f'run_{i}_repetition_{j}',
                    '__done': RunProgress.TODO
                }

                row_dict.update(base_row)

                if self.__data_columns:
                    for data_column in self.__data_columns:
                        row_dict[data_column] = " "

                experiment_run_table.append(row_dict)

        if self.__shuffle:
            random.shuffle(experiment_run_table)

        self.experiment_run_table = experiment_run_table
        return experiment_run_table
