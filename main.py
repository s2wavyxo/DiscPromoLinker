import tls_client
import os
import time
import random
import requests
import json
from loguru import logger
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle
import threading
import ctypes


logger.add("logs.txt", format="{time} {level} {message}", level="DEBUG", backtrace=True, diagnose=True)

global output_subfolder
USE_SEPERATE_FOLDERS = False
ThreadCount = 1
OneMonthLinked = 0 
ThreeMonthLinked = 0
Failed = 0

session = tls_client.Session(
    client_identifier="chrome133",
    random_tls_extension_order=True
)

UserAgent = ""
Sec_CH_UA = ""
SuperProperties = ""


def FetchHeaders():
    global UserAgent, Sec_CH_UA, SuperProperties

    logger.info("Fetching Headers")
    url = "https://api.s2tools.uk/headers/get"

    try:
        response = session.get(url)
    except Exception as e:
        logger.critical(f"Failed to fetch headers -> {e}")
        return False

    try:
        headers_data = response.json()
    except json.JSONDecodeError as e:
        logger.critical(f"Failed to decode response -> {e}")
        return False

    UserAgent = headers_data.get("User-Agent", "")
    Sec_CH_UA = headers_data.get("Sec-Ch-Ua", "")
    SuperProperties = headers_data.get("x-super-properties", "")

    if not UserAgent or not Sec_CH_UA or not SuperProperties:
        logger.critical("Missing required headers")
        return False

    logger.success("Fetched Headers")
    return True


def Startup():
    global output_subfolder, ThreadCount, USE_SEPERATE_FOLDERS
    tokens = ReadLines('tokens.txt')
    promos = ReadLines('promos.txt')
    proxies = ReadLines('proxies.txt')

    if len(tokens) == 0 or len(promos) == 0:
        logger.error("Tokens or promos file is empty.")
        input("Press [Enter] To Close The Program")
        return

    getHeaders = FetchHeaders()

    if not getHeaders:
        input("Press [Enter] To Close The Program")
        return 

    
    if not os.path.exists("output"):
        os.makedirs("output")

    USE_SEPERATE_FOLDERS = input("Use Different Output Folders? (y/n): ").lower() == "y"
    logger.info(f"User selected separate folders: {USE_SEPERATE_FOLDERS}")

    try:
        ThreadCount = int(input("How Many Threads? (1-100): ")) or 1
        if ThreadCount > 100:
            ThreadCount = 100
        logger.info(f"User selected thread count: {ThreadCount}")
    except ValueError:
        ThreadCount = 1
        logger.warning("Invalid thread count entered, defaulting to 1")


    if USE_SEPERATE_FOLDERS:
        current_time = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        output_subfolder = os.path.join("output", current_time)
        if not os.path.exists(output_subfolder):
            os.makedirs(output_subfolder)
    else:
        output_subfolder = "output"


    proxy_pool = cycle(proxies) if proxies else None

    with ThreadPoolExecutor(max_workers=ThreadCount) as executor:
        for token, promo in zip(tokens, promos):
            proxy = {"http": f"http://{next(proxy_pool)}"} if proxy_pool else None
            executor.submit(LinkPromo, token, promo, proxy)

        executor.shutdown(wait=True)

    input("Task Completed -> Press [Enter] To Close The Program")


file_lock = threading.Lock()

def ReadLines(file_path):
    with file_lock:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file.readlines()]

def RemoveLine(file_path, RemoveLine):
    try:
        with file_lock:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            with open(file_path, 'w', encoding='utf-8') as file:
                for line in lines:
                    if line.strip() != RemoveLine:
                        file.write(line)
    except Exception as e:
        logger.critical(f"Error writing to file {file_path}: {e}")

def AddLine(file_path, line):
    try:
        with file_lock:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'a', encoding='utf-8') as file:
                file.write(line + '\n')
    except Exception as e:
        logger.critical(f"Error writing to file {file_path}: {e}")


def FormatToken(token):
    if len(token) < 30:
        return token

    parts = token.split(".")

    if len(parts) < 3:
        return token

    masked_token = f"{parts[0]}.**.****"

    return masked_token

def FormatPromo(promo):
    parts = promo.rsplit('/', 1)  
    if len(parts) == 2:
        code = parts[1] 
        midpoint = len(code) // 2
        modified_code = code[:midpoint] + "****"
        return modified_code
    else:
        midpoint = len(promo) // 2
        return promo[:midpoint] + "****"


def UpdateTitle():
    global OneMonthLinked, ThreeMonthLinked, Failed
    while True:
        ctypes.windll.kernel32.SetConsoleTitleW(f"Streamlabs Promo Linker | discord.s2tools.uk | @s2wavy | 1 Month: {OneMonthLinked} | 3 Months: {ThreeMonthLinked} | Failed: {Failed}")
        time.sleep(1)

def LinkPromo(originalToken, originalPromo, proxy):
    global OneMonthLinked, ThreeMonthLinked, Failed, output_subfolder, UserAgent, Sec_CH_UA, SuperProperties

    token = originalToken.split(':')[-1]
    parts = originalPromo.split('/')
    if len(parts) >= 2:
        promotion_id = parts[-2] 
        jwt = parts[-1]
    else:
        RemoveLine("tokens.txt", originalToken)
        RemoveLine("promos.txt", originalPromo)
        AddLine(f'{output_subfolder}/incorrect_promo.txt', originalPromo)
        AddLine(f'{output_subfolder}/unused_token.txt', originalToken)
        logger.warning(f"Promo Incorrectly Formatted -> {FormatPromo(originalPromo)}|{FormatToken(originalToken)}")
        Failed += 1
        return


    PromoType = {"1310745123109339258": "3 Months", "1310745070936391821": "1 Month"}.get(promotion_id, "Unknown")

    payload = {
        "jwt": jwt,
    }


    url = f"https://discord.com/api/v9/entitlements/partner-promotions/{promotion_id}"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": Sec_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": UserAgent
    }


    try:
        response = session.post(url, headers=headers, json=payload, proxy=proxy)
    except Exception as e:
        RemoveLine("tokens.txt", originalToken)
        RemoveLine("promos.txt", originalPromo)

        AddLine(f'{output_subfolder}/failed_request_promo.txt', originalPromo)
        AddLine(f'{output_subfolder}/failed_request_token.txt', originalToken)
        logger.error(f"Exception Occured Failed To Link -> {FormatPromo(originalPromo)} To {FormatToken(originalToken)} | {response.status_code} - {response.text}")
        Failed += 1
        return


    if response.status_code == 200:
        #success
        try: 
            rJSON = response.json()
            promo_code = rJSON.get("code")
            if promo_code and promo_code != "":
                promo_code = f'https://promos.discord.gg/{promo_code}'
                combined = f'{originalToken}|{promo_code}'
                RemoveLine("tokens.txt", originalToken)
                RemoveLine("promos.txt", originalPromo)
                AddLine(f'{output_subfolder}/{PromoType}-linked_promo.txt', promo_code)
                AddLine(f'{output_subfolder}/{PromoType}-linked_token.txt', originalToken)
                AddLine(f'{output_subfolder}/{PromoType}-linked_combined.txt', combined)
                logger.success(f"Linked Promo -> {FormatPromo(promo_code)}|{FormatToken(originalToken)}")
                if PromoType == "1 Month":
                    OneMonthLinked += 1
                elif PromoType == "3 Months":
                    ThreeMonthLinked += 1
            else:
                RemoveLine("tokens.txt", originalToken)
                RemoveLine("promos.txt", originalPromo)
                AddLine(f'{output_subfolder}/failed_to_fetch_promo.txt', originalPromo)
                AddLine(f'{output_subfolder}/failed_to_fetch_token.txt', originalToken)
                logger.error(f"Failed To Fetch Promo -> {FormatPromo(originalPromo)}|{FormatToken(originalToken)} | {response.status_code} - {response.text}")
                Failed += 1
        except json.JSONDecodeError:
            RemoveLine("tokens.txt", originalToken)
            RemoveLine("promos.txt", originalPromo)
            AddLine(f'{output_subfolder}/failed_to_decode_promo.txt', originalPromo)
            AddLine(f'{output_subfolder}/failed_to_decode_token.txt', originalToken)
            logger.error(f"Failed To Decode Response -> {FormatPromo(originalPromo)}|{FormatToken(originalToken)} | {response.status_code} - {response.text}")
            Failed += 1
            return
    else:
        #failed
        RemoveLine("tokens.txt", originalToken)
        RemoveLine("promos.txt", originalPromo)

        AddLine(f'{output_subfolder}/failed_{response.status_code}_promo.txt', originalPromo)
        AddLine(f'{output_subfolder}/failed_{response.status_code}_token.txt', originalToken)

        logger.error(f"Failed To Link -> {FormatPromo(originalPromo)} To {FormatToken(originalToken)} | {response.status_code} - {response.text}")
        Failed += 1
        return


if __name__ == "__main__":
    threading.Thread(target=UpdateTitle, daemon=True).start()
    Startup()
