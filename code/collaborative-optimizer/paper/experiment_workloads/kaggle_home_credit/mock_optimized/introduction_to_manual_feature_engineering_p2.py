#!/usr/bin/env python


"""Optimized workload 3

This script is the optimized version of the workload 'introduction_to_manual_feature_engineering_p2'
which utilizes our Experiment Graph for optimizing the workload

"""
import warnings
# matplotlib and seaborn for plotting
from datetime import datetime

import matplotlib

from Reuse import LinearTimeReuse
from data_storage import DedupedStorageManager
from execution_environment import ExecutionEnvironment
from executor import CollaborativeExecutor
from experiment_graph.workload import Workload
from materialization_methods import StorageAwareMaterializer

matplotlib.use('ps')
import matplotlib.pyplot as plt
# numpy and pandas for data manipulation
import pandas as pd
import seaborn as sns

# Experiment Graph

# Suppress warnings
warnings.filterwarnings('ignore')


class introduction_to_manual_feature_engineering_p2(Workload):

    def run(self, execution_environment, root_data, verbose=0):

        def agg_numeric(df, parent_var, df_name):
            """Aggregates the numeric values in a dataframe. This can
            be used to create features for each instance of the grouping variable.

            Parameters
            --------
                df (dataframe):
                    the dataframe to calculate the statistics on
                group_var (string):
                    the variable by which to group df
                df_name (string):
                    the variable used to rename the columns

            Return
            --------
                agg (dataframe):
                    a dataframe with the statistics aggregated for
                    all numeric columns. Each instance of the grouping variable will have
                    the statistics (mean, min, max, sum; currently supported) calculated.
                    The columns are also renamed to keep track of features created.

            """
            df_columns = df.data(verbose=verbose).columns
            # Remove id variables other than grouping variable
            for col in df_columns:
                if col != parent_var and 'SK_ID' in col:
                    df = df.drop(columns=col)

            numeric_df = df.select_dtypes('number')

            # Group by the specified variable and calculate the statistics
            agg = numeric_df.groupby(parent_var).agg(['count', 'mean', 'max', 'min', 'sum'])

            # Need to create new column names
            column_names = [parent_var]
            columns = agg.data(verbose=verbose).columns
            for c in columns:
                if c != parent_var:
                    column_names.append('{}_{}'.format(df_name, c))
            return agg.set_columns(column_names)

        def agg_categorical(df, parent_var, df_name):
            """
            Aggregates the categorical features in a child dataframe
            for each observation of the parent variable.

            Parameters
            --------
            df : dataframe
                The dataframe to calculate the value counts for.

            parent_var : string
                The variable by which to group and aggregate the dataframe. For each unique
                value of this variable, the final dataframe will have one row

            df_name : string
                Variable added to the front of column names to keep track of columns


            Return
            --------
            categorical : dataframe
                A dataframe with aggregated statistics for each observation of the parent_var
                The columns are also renamed and columns with duplicate values are removed.

            """
            categorical = df.select_dtypes('object').onehot_encode()

            categorical = categorical.add_columns(parent_var, df[parent_var])

            # Groupby the group var and calculate the sum and mean
            categorical = categorical.groupby(parent_var).agg(['sum', 'count', 'mean'])

            column_names = [parent_var]
            columns = categorical.data(verbose=verbose).columns
            for c in columns:
                if c != parent_var:
                    column_names.append('{}_{}'.format(df_name, c))

            return categorical.set_columns(column_names)

        # Plots the distribution of a variable colored by value of the target
        def kde_target(var_name, df):
            # Calculate the correlation coefficient between the new variable and the target
            corr = df['TARGET'].corr(df[var_name])

            # Calculate medians for repaid vs not repaid
            avg_repaid = df[df['TARGET'] == 0][var_name].median()
            avg_not_repaid = df[df['TARGET'] == 1][var_name].median()

            plt.figure(figsize=(12, 6))

            # Plot the distribution for target == 0 and target == 1
            sns.kdeplot(df[df['TARGET'] == 0][var_name].dropna().data(verbose=verbose), label='TARGET == 0')
            sns.kdeplot(df[df['TARGET'] == 1][var_name].dropna().data(verbose=verbose), label='TARGET == 1')

            # label the plot
            plt.xlabel(var_name)
            plt.ylabel('Density')
            plt.title('%s Distribution' % var_name)
            plt.legend()

            # print out the correlation
            print('The correlation between %s and the TARGET is %0.4f' % (var_name, corr.data(verbose=verbose)))
            # Print out average values
            print('Median value for loan that was not repaid = %0.4f' % avg_not_repaid.data(verbose=verbose))
            print('Median value for loan that was repaid =     %0.4f' % avg_repaid.data(verbose=verbose))

        def return_size(df):
            """Return size of dataframe in gigabytes"""
            return round(df.compute_size() / 1e9, 2)

        previous = execution_environment.load(root_data + '/kaggle_home_credit/previous_application.csv')
        previous.head().data(verbose=verbose)

        # Calculate aggregate statistics for each numeric column
        previous_agg = agg_numeric(previous, 'SK_ID_CURR', 'previous')
        print('Previous aggregation shape: ', previous_agg.shape().data(verbose=verbose))
        previous_agg.head().data(verbose=verbose)

        # Calculate value counts for each categorical column
        previous_counts = agg_categorical(previous, 'SK_ID_CURR', 'previous')
        print('Previous counts shape: ', previous_counts.shape().data(verbose=verbose))
        previous_counts.head().data(verbose=verbose)

        train = execution_environment.load(root_data + '/kaggle_home_credit/application_train.csv')
        test = execution_environment.load(root_data + '/kaggle_home_credit/application_test.csv')

        test_labels = execution_environment.load(root_data + '/kaggle_home_credit/application_test_labels.csv')

        # Merge in the previous information
        train = train.merge(previous_counts, on='SK_ID_CURR', how='left')
        train = train.merge(previous_agg, on='SK_ID_CURR', how='left')

        test = test.merge(previous_counts, on='SK_ID_CURR', how='left')
        test = test.merge(previous_agg, on='SK_ID_CURR', how='left')

        # Function to calculate missing values by column# Funct
        def missing_values_table(dataset):
            # Total missing values
            mis_val = dataset.isnull().sum().data(verbose=verbose)

            mis_val_percent = 100 * mis_val / len(dataset.data(verbose=verbose))

            # Make a table with the results
            mis_val_table = pd.concat([mis_val, mis_val_percent], axis=1)
            # Rename the columns
            mis_val_table_ren_columns = mis_val_table.rename(columns={
                0: 'Missing Values',
                1: '% of Total Values'
            })
            # Sort the table by percentage of missing descending
            mis_val_table_ren_columns = mis_val_table_ren_columns[
                mis_val_table_ren_columns.iloc[:, 1] != 0].sort_values(
                '% of Total Values', ascending=False).round(1)

            # Print some summary information
            print("Your selected dataframe has " + str(dataset.shape().data(verbose=verbose)[1]) + " columns.\n"
                                                                                                   "There are " + str(
                mis_val_table_ren_columns.shape[0]) +
                  " columns that have missing values.")

            # Return the dataframe with missing information
            return mis_val_table_ren_columns

        def remove_missing_columns(train, test, threshold=90):

            # Total missing values
            train_miss = train.isnull().sum().data(verbose=verbose)
            train_miss_percent = 100 * train_miss / train.shape().data(verbose=verbose)[0]

            # Total missing values
            test_miss = test.isnull().sum().data(verbose=verbose)
            test_miss_percent = 100 * test_miss / test.shape().data(verbose=verbose)[0]

            # list of missing columns for train and test
            missing_train_columns = list(train_miss.index[train_miss_percent > threshold])
            missing_test_columns = list(test_miss.index[test_miss_percent > threshold])

            # Combine the two lists together
            missing_columns = list(set(missing_train_columns + missing_test_columns))

            # Print information
            print('There are %d columns with greater than %d%% missing values.' % (len(missing_columns), threshold))

            # Drop the missing columns and return
            train = train.drop(columns=missing_columns)
            test = test.drop(columns=missing_columns)

            return train, test

        train, test = remove_missing_columns(train, test)

        def aggregate_client(df, group_vars, df_names):
            """Aggregate a dataframe with data at the loan level
            at the client level

            Args:
                df (dataframe): data at the loan level
                group_vars (list of two strings): grouping variables for the loan
                and then the client (example ['SK_ID_PREV', 'SK_ID_CURR'])
                df_names (list of two strings): names to call the resulting columns
                (example ['cash', 'client'])

            Returns:
                df_client (dataframe): aggregated numeric stats at the client level.
                Each client will have a single row with all the numeric data aggregated
            """

            # Aggregate the numeric columns
            df_agg = agg_numeric(df, parent_var=group_vars[0], df_name=df_names[0])

            # If there are categorical variables
            if any(df.dtypes().data(verbose=verbose) == 'category'):

                # Count the categorical columns
                df_counts = agg_categorical(df, parent_var=group_vars[0], df_name=df_names[0])

                # Merge the numeric and categorical
                df_by_loan = df_counts.merge(df_agg, on=group_vars[0], how='outer')

                # Merge to get the client id in dataframe
                df_by_loan = df_by_loan.merge(df[[group_vars[0], group_vars[1]]], on=group_vars[0], how='left')

                # Remove the loan id
                df_by_loan = df_by_loan.drop(columns=[group_vars[0]])

                # Aggregate numeric stats by column
                df_by_client = agg_numeric(df_by_loan, parent_var=group_vars[1], df_name=df_names[1])

            # No categorical variables
            else:
                # Merge to get the client id in dataframe
                df_by_loan = df_agg.merge(df[[group_vars[0], group_vars[1]]], on=group_vars[0], how='left')

                # Remove the loan id
                df_by_loan = df_by_loan.drop(columns=[group_vars[0]])

                # Aggregate numeric stats by column
                df_by_client = agg_numeric(df_by_loan, parent_var=group_vars[1], df_name=df_names[1])

            return df_by_client

        cash = execution_environment.load(root_data + '/kaggle_home_credit/POS_CASH_balance.csv')
        cash.head()

        cash_by_client = aggregate_client(cash, group_vars=['SK_ID_PREV', 'SK_ID_CURR'], df_names=['cash', 'client'])
        cash_by_client.head()

        print
        'Cash by Client Shape: {}'.format(cash_by_client.shape().data(verbose=verbose))
        train = train.merge(cash_by_client, on='SK_ID_CURR', how='left')
        test = test.merge(cash_by_client, on='SK_ID_CURR', how='left')

        train, test = remove_missing_columns(train, test)
        train.data()
        test.data()

        return True


if __name__ == "__main__":
    ROOT = '/Users/bede01/Documents/work/phd-papers/published/ml-workload-optimization'
    root_data = ROOT + '/data'

    workload = introduction_to_manual_feature_engineering_p2()

    mat_budget = 16.0 * 1024.0 * 1024.0
    sa_materializer = StorageAwareMaterializer(storage_budget=mat_budget)

    ee = ExecutionEnvironment(DedupedStorageManager(), reuse_type=LinearTimeReuse.NAME)
    # database_path = \
    #     root_data + '/experiment_graphs/kaggle_home_credit/introduction_to_manual_feature_engineering_p2/sa_16'
    # if os.path.exists(database_path):
    #     ee.load_history_from_disk(database_path)
    executor = CollaborativeExecutor(execution_environment=ee, materializer=sa_materializer)
    execution_start = datetime.now()

    executor.end_to_end_run(workload=workload, root_data=root_data, verbose=1)
    # executor.store_experiment_graph(database_path)
    execution_end = datetime.now()
    elapsed = (execution_end - execution_start).total_seconds()

    print('finished execution in {} seconds'.format(elapsed))
