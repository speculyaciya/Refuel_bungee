from web3 import Web3
from loguru import logger as global_logger
import settings_refuel as s
import config as c
import time
import ZBC
from decimal import Decimal
import copy
import random

def refuel(name, proxy, private_key, amount, from_chain, to_chain):
    global_logger.remove()
    logger = copy.deepcopy(global_logger)
    logger.add(
        fr'log_wallet\log_{name}.log',
        format="<white>{time: MM/DD/YYYY HH:mm:ss}</white> | <level>"
        "{level: <8}</level> | <cyan>"
        "</cyan> <white>{message}</white>")
    
    ROUND = 6
    tmp = ''
    if amount == 999.0:
        tmp = 1
    amount = round(Decimal(amount), ROUND)
    log_name = f'Refuel {amount} {from_chain} to {to_chain}'

    _element = 'chain'
    from_data = ZBC.search_setting_data_by_element(element_search = _element, value=from_chain, list=s.CHAIN_LIST)
    if len(from_data) == 0:
        logger.error(f'{name} | {log_name} | Ошибка при поиске информации {_element}')
        return False
    else:
        from_data = from_data[0]

    _element = 'chain'
    to_data = ZBC.search_setting_data_by_element(element_search = _element, value=to_chain, list=s.CHAIN_LIST)
    if len(to_data) == 0:
        logger.error(f'{name} | {log_name} | Ошибка при поиске информации {_element}')
        return False
    else:
        to_data = to_data[0]

    RPC_FROM        = from_data['rpc']
    REFUEL          = from_data['contract']
    REFUEL_ABI      = from_data['abi']
    MAX_GAS         = c.MAX_GAS

    RPC_TO          = to_data['rpc']
    CHAIN_ID        = to_data['chain_id']

    # Сначала коннектимся к нужной RPC
    w3_from = Web3(Web3.HTTPProvider(RPC_FROM, request_kwargs={"proxies":{'https' : proxy, 'http' : proxy }, 'timeout': 180}))
    if w3_from.is_connected() == True:
        account = w3_from.eth.account.from_key(private_key)
        address = account.address
        logger.success(f'{name} | {address} | {log_name} | Подключились к {from_chain} | {RPC_FROM}')
    else:
        logger.error(f'{name} | {log_name} | Ошибка при подключении к {from_chain} | {RPC_FROM}')
        return False
    w3_to = Web3(Web3.HTTPProvider(RPC_TO, request_kwargs={"proxies":{'https' : proxy, 'http' : proxy }, 'timeout': 180}))
    if w3_to.is_connected() == True:
        logger.success(f'{name} | {address} | {log_name} | Подключились к {to_chain} | {RPC_TO}')
    else:
        logger.error(f'{name} | {log_name} | Ошибка при подключении к {to_chain} | {RPC_TO}')
        return False

    #   Получаем до в to_chain 
    balance_to = w3_to.eth.get_balance(address)
    balance_from = w3_from.eth.get_balance(address)
    if tmp == 1:
        amount = balance_from
        tmp = 'all'
    human_balance_to = round(w3_to.from_wei(balance_to, "ether").real, ROUND)
    logger.info(f'{name} | {address} | {log_name} | {human_balance_to}, {to_chain}')
    
    # Делаем refuel 
    try:
        if tmp == 'all':
            value = amount
        else:
            value = w3_from.to_wei(amount, "ether")
        contractREFUEL = w3_from.eth.contract(address=w3_from.to_checksum_address(REFUEL), abi=REFUEL_ABI)
        nonce = w3_from.eth.get_transaction_count(address)
        while True:
            # Узнаем GAS
            gas = contractREFUEL.functions.depositNativeToken(
                int(CHAIN_ID),
                address,
                ).estimate_gas({'from': address, 'value':value , 'nonce': nonce })
            gas = gas * 1.2
            gas_price = w3_from.eth.gas_price
            txCost = gas * gas_price
            txCostInEther = round(w3_from.from_wei(txCost, "ether").real,ROUND)
            if txCostInEther < MAX_GAS:
                logger.info(f'{name} | {address} | {log_name} | Стоимость газа на REFUEL {txCostInEther}, {from_chain}')
                break
            else:
                logger.warning(f'{name} | {address} | {log_name} | Стоимость газа на REFUEL {txCostInEther}, {from_chain}, это больше максимума')
                time.sleep(30)
                continue

        # Выполняем REFUEL
        transaction = contractREFUEL.functions.depositNativeToken(
            int(CHAIN_ID),
            address,
            ).build_transaction({
                'from': address,
                'value': round(value - txCost),
                'gas': int(gas),
                'gasPrice': w3_from.eth.gas_price,
                'nonce': nonce})
        signed_transaction = account.sign_transaction(transaction)
        transaction_hash = w3_from.eth.send_raw_transaction(signed_transaction.rawTransaction)
        logger.success(f'{name} | {address} | {log_name} | Подписали REFUEL {transaction_hash.hex()}')
        time.sleep(60)
        status = ZBC.transaction_verification(name, transaction_hash, w3_from, log_name=log_name, text=f'REFUEL {from_chain} to {to_chain} кол-во {amount}')
        if status == False:
            logger.error(f'{name} | {address} | {log_name} | Ошибка при REFUEL {from_chain} to {to_chain} кол-во {amount}')
            return False
    except Exception as Ex:
        if "insufficient funds for gas * price + value" in str(Ex):
            logger.error(f'{name} | {address} | {log_name} | Недостаточно средств для REFUEL {from_chain} to {to_chain}, кол-во {amount} \n {str(Ex)}')
            return False
        logger.error(f'{name} | {address} | {log_name} | Ошибка при REFUEL {from_chain} to {to_chain}, кол-во {amount}  \n {str(Ex)}')
        return False

    # Проверяем баланс кошелька на который отправили
    try:
        lv_count = 0
        while lv_count <= 360:
            try:
                balance_to2 = w3_to.eth.get_balance(address)
            except Exception as Ex:
                logger.error(f'{name} | {address} | {log_name} | Ошибка при balanceOf, {Ex}')
                time.sleep(60)
                continue
            human_balance_to2 = round(w3_to.from_wei(balance_to2, "ether").real, ROUND)
            logger.info(f'{name} | {address} | {log_name} | {human_balance_to2}, {to_chain}') 
            if balance_to < balance_to2:
                logger.success(f'{name} | {address} | {log_name} | {human_balance_to2}, REFUEL выполнен') 
                return True
            lv_count += 1
            time.sleep(60)
        logger.error(f'{name} | {address} | {log_name} | {balance_to2}, не получили сумму от REFUEL') 
        return False
    except Exception as Ex:
        logger.error(f'{name} | {address} | {log_name} | Ошибка при проверке перевода кол-во {amount}  \n {str(Ex)}')
        return False
