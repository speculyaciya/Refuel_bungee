from loguru import logger as global_logger
import sys
import random
import pandas as pd
import execute_util
import settings_refuel as s
import config as c
from refuel import refuel
import datetime
import time
import copy

def execute(data_csv, row, index) -> dict({'status':bool, 'text':str}):
    prelog = f'{row["Name"]} | {row["Wallet"]}'
    logger.info(f'Выполеняется {prelog}')
    activity = execute_util.generate_activity(row=row)
    if activity == s.NO_ACTIVITY:
        data_csv.loc[index,'DO'] = 'DONE'
        logger.warning(f'{prelog} | Активностей больше нет')
        return data_csv
    logger.info(f'{prelog} | Выполняется {activity}')
    
    result = refuel(
        name        = row['Name'],
        proxy       = row['Proxy'],
        private_key = row['Private_key'], 
        amount      = float(row[f'{activity}_VALUE']),
        from_chain  = c.FROM_CHAIN,
        to_chain    = activity.lower().capitalize(),
    )
    
    if result == True:
        data_csv.loc[index,f'{activity}'] = 'DONE'
        logger.success(f'{prelog} | Выполнено {activity}')
    else:
        logger.error(f'{prelog} | Ошибка {activity}')

    return data_csv

if __name__ == '__main__':
    global_logger.remove()
    logger = copy.deepcopy(global_logger)
    logger.add(sys.stderr,
           format="<white>{time: MM/DD/YYYY HH:mm:ss}</white> | <level>"
           "{level: <8}</level> | <cyan>"
           "</cyan> <white>{message}</white>")
    logger.add('refuel.log',
           format="<white>{time: MM/DD/YYYY HH:mm:ss}</white> | <level>"
           "{level: <8}</level> | <cyan>"
           "</cyan> <white>{message}</white>")

    csv_path = ('data.csv')

    while True:
        do_index_list = []
        data_csv = pd.read_csv(csv_path,keep_default_na=False)
        for index, row in data_csv.iterrows():
            if row['DO'] == 'X':
                do_index_list.append(index)
        if len(do_index_list) == 0:
            break
        execute_index = random.choice(do_index_list)
        row = data_csv.loc[execute_index]
        data_csv = execute(data_csv=data_csv, row=row, index=execute_index)
        data_csv.to_csv(csv_path, index=False)
        wait_time = random.sample(c.WAIT_MIN,1)[0]
        nextTime = datetime.datetime.now() + datetime.timedelta(minutes=wait_time)
        logger.info(f'Следующий запуск {nextTime}')
        while True:
            if datetime.datetime.now() > nextTime:
                break
            time.sleep(60)