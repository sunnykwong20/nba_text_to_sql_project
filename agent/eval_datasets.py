from langsmith import Client
import csv
from pathlib import Path
import os
from dotenv import load_dotenv
import glob
import pandas as pd
import json

### eval_datasets: Makes the evaluation datasets needed to run AI Agent Evaluations


# loads enviroment variables
DB_PATH = "data/nba.sqlite"
script_dir = Path(__file__).resolve().parent
env_path = script_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

## Gets the client to langsmith, sets dataset name
nba_text_to_sql_eval_client = Client()
dataset_name = "NBA Text-to-SQL Eval Results"

tabular_folder_path = Path("agent/eval_dataset_results/table_results")
csv_files = glob.glob(f"{tabular_folder_path}/*.csv")

## Gathers CSV to question answeres
table_results_data_base_dict = {}
for csv_file in csv_files:
    table_results_data_base_dict[csv_file.split('\\')[-1].replace('.csv','')] = pd.read_csv(csv_file)

examples = [


    #### Questions that are supposed to end with tabular data

    ### Question 1 for tables
    {
        "inputs":{"question":"What were the top 5 teams by win percentage in the 2015-16 regular season?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_1'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}

    }    

    ### Question 2 for tables
    ,{
        "inputs":{"question":"List every team's win-loss record for the 1995-96 season, sorted by wins descending."}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_2'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}

    }    

    ### Question 3 for tables
    ,{
        "inputs":{"question":"Who were the first overall draft picks each year from 2015 to 2020?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_3'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}
    }   

    ### Question 4 for tables
    ,{
        "inputs":{"question":"What are the top 5 teams by points per game in the 2022-23 season?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_4'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}
    }    

    ### Question 5 for tables
    ,{
        "inputs":{"question":"Which 5 teams had the most wins all-time across the seasons in this database?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_5'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}

    }    

    ### Question 6 for tables
    ,{
        "inputs":{"question":"List the conference rank and division rank for all teams in the 2021-22 season."}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_6'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}
    }    

    ### Question 7 for tables
    , {
        "inputs":{"question":"What are the 5 highest-scoring games (by total combined points) in the game table?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_7'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}
    }   

    ### Question 8 for tables
    , {
        "inputs":{"question":"Which teams reached 60+ wins in a season, and how many times did each team do it?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": json.loads(table_results_data_base_dict['question_8'].to_json(orient='records'))
        }
        ,"metadata": {"category":"clean","response_format":"table"}
    }   

    #### Questions that are supposed to end with a narrative

    ### Question 1 for narrative
    , {
        "inputs":{"question":"Did the Golden State Warriors' win percentage improve from the 2014-15 season to the 2015-16 season?"}
        ,"outputs":{
            "conversational_answer": "Yes. They improved from .817 to .89"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   


    ### Question 2 for narrative
    , {
        "inputs":{"question":"How did the Chicago Bulls perform in the 1995-96 season?"}
        ,"outputs":{
            "conversational_answer": "They had 72 wins and 10 losses. They ranked 1st in their conference and first in their division"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 3 for narrative
    , {
        "inputs":{"question":"Was there ever a season where a team won 70 or more games?"}
        ,"outputs":{
            "conversational_answer": "Yes. There were two season. 1995-1996 and 2015-2016"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 4 for narrative
    , {
        "inputs":{"question":"Which team had a better record in 2018-19, the Raptors or the Warriors?"}
        ,"outputs":{
            "conversational_answer": "The Raptors had the better record"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 5 for narrative
    , {
        "inputs":{"question":"What was the biggest margin of victory in a single game in the game table?"}
        ,"outputs":{
            "conversational_answer": "The Memphis Grizzlies vs the Oklahoma City Thunder by 73 Points. "
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 6 for narrative
    , {
        "inputs":{"question":"Which team recorded the most fast break points in a single game, and how many?"}
        ,"outputs":{
            "conversational_answer": "The Phoenix Suns with 56 fast_break points"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 7 for narrative
    , {
        "inputs":{"question":"How many teams had a losing record in 2019-20?"}
        ,"outputs":{
            "conversational_answer": "17 Teams"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ### Question 8 for narrative
    ,{
        "inputs":{"question":"Who was selected with the very first pick in the 2003 NBA draft?"}
        ,"outputs":{
            "conversational_answer": "Lebron James"
            , "data_table": None
        }
        ,"metadata": {"category":"clean","response_format":"narrative"}
    }   

    ###### Questions where a refusal is expected

    ### Question 1 for Refusal: nothing to do with basketball
    , {
        "inputs":{"question":"What's the meaning of life?"}
        ,"outputs":{
            "conversational_answer": None        
            , "data_table": None
        }
        ,"metadata": {"category":"out_of_scope","response_format":"out_of_scope"}
    }

    ### Question 2 for Refusal: Wrong Sport
    , {
        "inputs":{"question":"How many touchdowns did the Celtics score in 2015?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": None
        }
        ,"metadata": {"category":"out_of_scope","response_format":"out_of_scope"}
    }

    ### Question 3 for Refusal: Future season, can't query
    , {
        "inputs":{"question":"What will the Lakers' record be in the 2030-31 season?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": None
        }
        ,"metadata": {"category":"out_of_scope","response_format":"out_of_scope"}
    }

    ### Question 4 for Refusal: Can't do this yet
    , {
        "inputs":{"question":"Who scored the most points in Game 7 of the 2016 NBA Finals?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": None
        }
        ,"metadata": {"category":"out_of_scope","response_format":"out_of_scope"}
    }

    ### Question 5 for Refusal: Wrong Sport
    , {
        "inputs":{"question":"What's the average batting average of players drafted after 2010?"}
        ,"outputs":{
            "conversational_answer": None
            , "data_table": None
        }
        ,"metadata": {"category":"out_of_scope","response_format":"out_of_scope"}
    }
]

## Uploads Evaluation Datasets to Langsmith
dataset = nba_text_to_sql_eval_client.create_dataset(dataset_name=dataset_name)
nba_text_to_sql_eval_client.create_examples(dataset_id=dataset.id, examples=examples)