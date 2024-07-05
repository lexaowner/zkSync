from web3 import Web3
import json as js
import time
from utils.approve import Approve
import requests
from utils.tg_bot import TgBot
from requests import ConnectionError
from requests.adapters import Retry
from web3.exceptions import TransactionNotFound


class OneInch(Approve, TgBot):

    """  """

    def __init__(self, private_key, web3, number, log):
        super().__init__(private_key, web3, number, log)
        self.web3 = web3
        self.number = number
        self.log = log
        self.private_key = private_key
        self.address_wallet = self.web3.eth.account.from_key(private_key).address
        self.token_abi = js.load(open('./abi/erc20.txt'))

    def buy_token(self, token_to_buy, value_eth, retry=0):
        self.log.info('Buy token 1inch')
        from_token_address = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
        try:
            balance = self.web3.eth.get_balance(self.address_wallet)
            value = Web3.to_wei(value_eth, 'ether')
            if value > balance:
                value = balance - Web3.to_wei(0.003, 'ether')
                if value < Web3.to_wei(0.000001, 'ether'):
                    self.log.info('Insufficient funds')
                    return 'balance'
            _1inchurl = f'https://api.1inch.io/v5.0/324/swap?fromTokenAddress={from_token_address}&\
toTokenAddress={token_to_buy}&amount={Web3.to_wei(value_eth, "ether")}&fromAddress={self.address_wallet}&slippage=3'

            res = requests.get(url=_1inchurl, timeout=600)
            json_data = res.json()
            min_tok = round(Web3.from_wei(int(json_data['toTokenAmount']), 'picoether'), 3)
            txn = {
                'chainId': 324,
                'data': json_data['tx']['data'],
                'from': self.address_wallet,
                'to': Web3.to_checksum_address(json_data['tx']['to']),
                'value': int(json_data['tx']['value']),
                'nonce': self.web3.eth.get_transaction_count(self.address_wallet),
                'gasPrice': self.web3.eth.gas_price,
                'gas': json_data['tx']['gas']
            }
            gas = self.web3.eth.estimate_gas(txn)
            txn.update({'gas': gas})

            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            self.log.info(f'Transaction sent: https://explorer.zksync.io/tx/{Web3.to_hex(tx_hash)}')
            hash_ = str(Web3.to_hex(tx_hash))
            time.sleep(20)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300, poll_latency=20)
            if tx_receipt.status == 1:
                self.log.info('Transaction confirmed')            
            else:
                self.log.info('Transaction failed. Try again')
                if TgBot.TG_BOT_SEND is True:
                    TgBot.send_message_error(self, self.number, 'Buy token 1inch', self.address_wallet,
                                             'Transaction failed. Try again')
                time.sleep(60)
                retry += 1
                if retry > 5:
                    return 0
                self.buy_token(token_to_buy, value_eth, retry)
                return

            self.log.info(f'[{self.number}] Buy {min_tok} USDC 1inch || https://explorer.zksync.io/tx/{hash_}\n')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_success(self, self.number, f'Buy {min_tok} USDC 1inch', self.address_wallet,
                                           f'https://explorer.zksync.io/tx/{hash_}')
        except TransactionNotFound:
            self.log.info('Transaction not found for a while. Try again')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_error(self, self.number, 'Buy token 1inch', self.address_wallet,
                                         'Transaction not found for a while. Try again')
            time.sleep(120)
            retry += 1
            if retry > 5:
                return 0
            self.buy_token(token_to_buy, value_eth, retry)

        except ConnectionError:
            self.log.info('Connection error')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_error(self, self.number, 'Buy token 1inch', self.address_wallet,
                                         'Connection error')
            time.sleep(120)
            retry += 1
            if retry > 5:
                return 0
            self.buy_token(token_to_buy, value_eth, retry)

        except Exception as error:
            if isinstance(error.args[0], dict):
                if 'insufficient funds' in error.args[0]['message']:
                    self.log.info('insufficient funds')
                    if TgBot.TG_BOT_SEND is True:
                        TgBot.send_message_error(self, self.number, 'Buy token 1inch', self.address_wallet,
                                                 'insufficient funds')
                    return 'balance'
            else:
                self.log.info(error)
                time.sleep(120)
                retry += 1
                if retry > 5:
                    return 0
                self.buy_token(token_to_buy, value_eth, retry)

    def sold_token(self, token_to_sold, retry=0):
        self.log.info('Sold token 1inch')
        try:
            token_contract = self.web3.eth.contract(address=token_to_sold, abi=self.token_abi)
            token_balance = token_contract.functions.balanceOf(self.address_wallet).call()
            decimal = token_contract.functions.decimals().call()
            from_token_address = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
            spender = Web3.to_checksum_address('0x6e2b76966cbd9cf4cc2fa0d76d24d5241e0abc2f')
            allowance = token_contract.functions.allowance(self.address_wallet, spender).call()
            if allowance < 100000 * 10 ** decimal:
                self.log.info('Waiting for approve')
                self.approve(token_to_sold, spender)
                time.sleep(60)

            _1inchurl = f'https://api.1inch.io/v5.0/324/swap?fromTokenAddress={token_to_sold}&\
toTokenAddress={from_token_address}&amount={token_balance}&fromAddress={self.address_wallet}&slippage=3'

            res = requests.get(url=_1inchurl, timeout=600)
            json_data = res.json()
        except Exception as error:
            self.log.info(error)
            time.sleep(60)
            self.sold_token(token_to_sold)
        try:
            min_tok = round(Web3.from_wei(token_balance, 'picoether'), 3)
            gas = json_data['tx']['gas']
            txn = {
                'chainId': 324,
                'data': json_data['tx']['data'],
                'from': self.address_wallet,
                'to': spender,
                'nonce': self.web3.eth.get_transaction_count(self.address_wallet),
                'gasPrice': self.web3.eth.gas_price,
                'gas': gas
            }

            gas = self.web3.eth.estimate_gas(txn)
            txn.update({'gas': gas})

            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            self.log.info(f'Transaction sent: https://explorer.zksync.io/tx/{Web3.to_hex(tx_hash)}')
            hash_ = str(Web3.to_hex(tx_hash))
            time.sleep(15)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300, poll_latency=20)
            if tx_receipt.status == 1:
                self.log.info('Transaction confirmed')            
            else:
                self.log.info(f'Transaction failed. Try again')
                if TgBot.TG_BOT_SEND is True:
                    TgBot.send_message_error(self, self.number, 'Sold token 1inch', self.address_wallet,
                                             'Transaction failed. Try again')
                time.sleep(60)
                retry += 1
                if retry > 5:
                    return 0
                self.sold_token(token_to_sold, retry)
                return

            self.log.info(f'[{self.number}] Sold {min_tok} USDC 1inch || https://explorer.zksync.io/tx/{hash_}\n')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_success(self, self.number, f'Sold {min_tok} USDC 1inch', self.address_wallet,
                                           f'https://explorer.zksync.io/tx/{hash_}')
        except TransactionNotFound:
            self.log.info('Transaction not found for a while. Try again')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_error(self, self.number, 'Sold token 1inch', self.address_wallet,
                                         'Transaction not found for a while. Try again')
            time.sleep(120)
            retry += 1
            if retry > 5:
                return 0
            self.sold_token(token_to_sold, retry)
        except ConnectionError:
            self.log.info('Connection error')
            if TgBot.TG_BOT_SEND is True:
                TgBot.send_message_error(self, self.number, 'Sold token 1inch', self.address_wallet,
                                         'Connection error')
            time.sleep(120)
            retry += 1
            if retry > 5:
                return 0
            self.sold_token(token_to_sold, retry)
        except Exception as error:
            if isinstance(error.args[0], dict):
                if 'insufficient funds' in error.args[0]['message']:
                    self.log.info('insufficient funds')
                    if TgBot.TG_BOT_SEND is True:
                        TgBot.send_message_error(self, self.number, 'Sold token 1inch', self.address_wallet,
                                                 'insufficient funds')
                    return 'balance'
            else:
                self.log.info(error)
                time.sleep(120)
                retry += 1
                if retry > 5:
                    return 0
                self.sold_token(token_to_sold, retry)
