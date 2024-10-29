import sys
import os
import argparse
import subprocess
import requests
import zipfile
import datetime
import platform
from bs4 import BeautifulSoup
from loguru import logger
import tarfile

# Configure logging
logger.add("app.log", rotation="500 MB", level="INFO")

def download_file(url, save_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        logger.info(f"Downloaded file from {url} to {save_path}")
    else:
        logger.error(f"Failed to download file from {url} with status code {response.status_code}")
        response.raise_for_status()

def setup_sqlmap():
    if not os.path.exists('sqlmap/sqlmap.py'):
        logger.info("SQLMap not found, downloading...")
        sqlmap_zip_url = 'https://github.com/sqlmapproject/sqlmap/archive/refs/heads/master.zip'
        download_file(sqlmap_zip_url, 'sqlmap.zip')
        with zipfile.ZipFile('sqlmap.zip', 'r') as zip_ref:
            zip_ref.extractall()
        os.rename('sqlmap-master', 'sqlmap')
        logger.info("SQLMap downloaded and extracted.")
        os.unlink('sqlmap.zip')
    else:
        logger.info("SQLMap is already set up.")
    sys.path.append(os.path.abspath('./sqlmap'))

def install_ruby_windows():
    logger.info("Checking for Ruby installation...")
    try:
        ruby_version = subprocess.run(['ruby', '--version'], check=True, capture_output=True, text=True)
        logger.info(f"Ruby is already installed: {ruby_version.stdout.split()[1]}")
    except subprocess.CalledProcessError:
        logger.info("Ruby not found, installing...")
        ruby_installer_url = 'https://github.com/oneclick/rubyinstaller2/releases/latest/download/rubyinstaller-3.1.2-1-x64.exe'
        installer_path = 'rubyinstaller.exe'
        download_file(ruby_installer_url, installer_path)
        logger.info("Running Ruby installer, please follow the prompts if any...")
        subprocess.run([installer_path, '/verysilent', '/dir="C:\\Ruby31-x64"'], check=True)
        logger.info("Ruby installed successfully.")
        os.unlink(installer_path)

def setup_cewl():
    os_detected = platform.system()
    try:
        subprocess.run(['cewl', '-h'], check=True, capture_output=True)
        logger.info("CEWL is already installed.")
    except subprocess.CalledProcessError:
        logger.info("CEWL not found, downloading and installing...")
        cewl_git_url = 'https://github.com/digininja/CeWL.git'
        subprocess.check_call(['git', 'clone', cewl_git_url, 'CeWL'])
        os.chdir('CeWL')
        if os_detected == "Windows":
            install_ruby_windows()
            subprocess.run(['gem', 'install', 'bundler', '--no-document'], check=True)
            subprocess.run(['bundle', 'install'], check=True)
        os.chdir('..')
        logger.info("CEWL downloaded and installed.")
        if os_detected != "Windows":
            os.environ['PATH'] += os.pathsep + os.path.abspath('./CeWL')

def setup_dirbuster():
    dirbuster_jar = os.path.abspath('./DirBuster-1.0-RC1/DirBuster-1.0-RC1.jar')
    if os.path.exists(dirbuster_jar):
        logger.info("DirBuster is already installed.")
        return dirbuster_jar
    else:
        logger.info("DirBuster not found, downloading and installing...")
        dirbuster_tar_url = 'https://sourceforge.net/projects/dirbuster/files/DirBuster%20%28jar%20%2B%20source%29/1.0-RC1/DirBuster-1.0-RC1.tar.bz2/download'
        download_file(dirbuster_tar_url, 'dirbuster.tar.bz2')
        with tarfile.open('dirbuster.tar.bz2', 'r:bz2') as tar_ref:
            tar_ref.extractall()
        os.unlink('dirbuster.tar.bz2')
        logger.info("DirBuster downloaded and installed.")
        return dirbuster_jar

def run_dirbuster(ip_address, wordlist_file):
    dirbuster_jar = setup_dirbuster()
    if dirbuster_jar is None:
        logger.error("Failed to set up DirBuster. Exiting.")
        return None

    if not os.path.exists(dirbuster_jar):
        logger.error(f"DirBuster JAR file not found at {dirbuster_jar}")
        return None

    logger.info(f"Scanning target '{ip_address}' with DirBuster...")

    output_file = f'dirbuster_results_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.txt'
    dirbuster_command = [
        'java', '-jar', dirbuster_jar, '-H', '-u', f'http://{ip_address}', '-l', wordlist_file,
        '-t', '50', '-e', 'php,html', '-o', output_file
    ]
    subprocess.run(dirbuster_command, check=True)

    return output_file

def install_tools():
    setup_sqlmap()
    setup_cewl()
    setup_dirbuster()
    try:
        import loguru
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'loguru'], check=True)
        logger.info("Loguru installed.")
    try:
        import requests
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], check=True)
        logger.info("Requests library installed.")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4'], check=True)
        logger.info("BeautifulSoup installed.")

def find_input_fields(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.find_all('input')

def send_to_sqlmap(input_details):
    sqlmap_server = 'http://localhost:8775'
    task_new = f'{sqlmap_server}/task/new'
    task_id = requests.get(task_new).json()['taskid']
    start_url = f'{sqlmap_server}/scan/{task_id}/start'
    headers = {'Content-Type': 'application/json'}

    data = {
        "url": input_details['url'],
        "data": input_details.get('data', '')
    }

    response = requests.post(start_url, json=data, headers=headers)
    return response.json()

def generate_wordlist(target):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    wordlist_filename = f"wordlist_{timestamp}.txt"
    cewl_command = f"cewl {target} -w {wordlist_filename}"
    result = subprocess.run(cewl_command, shell=True)
    if result.returncode != 0:
        logger.error("Failed to generate wordlist. Please check that CEWL is correctly installed and configured.")
        return None
    logger.info(f"Generated wordlist saved as: {wordlist_filename}")
    return wordlist_filename

def parse_dirbuster_results(file_path):
    urls = []
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('http'):
                urls.append(line.strip())
    return urls

def run_sqlmap(urls):
    for url in urls:
        logger.info(f"Running SQLMap on {url}")
        input_details = {
            "url": url
        }
        result = send_to_sqlmap(input_details)
        if 'success' in result:
            logger.info(f"SQL injection successful on {url}")
            logger.info("Command executed by SQLMap:")
            logger.info(result['command'])
        else:
            logger.info(f"SQL injection unsuccessful on {url}")

def main():
    parser = argparse.ArgumentParser(description='OWASP Fuzzer Pro - A tool for web application security testing.')
    parser.add_argument('-s', help='IP address or website URL of the server to test')
    parser.add_argument('wordlistFileName', nargs='?', help='Filename of the wordlist to use')
    parser.add_argument('-c', help='Generate a wordlist using CEWL for the given IP or website', metavar='TARGET')
    parser.add_argument('-i', '--install', help='Install and setup all necessary tools (SQLMap, CEWL, and DirBuster)',
                        action='store_true')

    args = parser.parse_args()

    if args.install:
        install_tools()
    elif args.c:
        setup_cewl()
        wordlist_file = generate_wordlist(args.c)
        if wordlist_file:
            dirbuster_output = run_dirbuster(args.c,

 wordlist_file)
            if dirbuster_output:
                urls = parse_dirbuster_results(dirbuster_output)
                run_sqlmap(urls)
    elif args.s and args.wordlistFileName:
        setup_sqlmap()
        dirbuster_output = run_dirbuster(args.s, args.wordlistFileName)
        if dirbuster_output:
            urls = parse_dirbuster_results(dirbuster_output)
            run_sqlmap(urls)

def print_banner():
    print("""
####### #     #    #     #####  ######     ####### #     # ####### ####### ####### ######
#     # #  #  #   # #   #     # #     #    #       #     #      #       #  #       #     #
#     # #  #  #  #   #  #       #     #    #       #     #     #       #   #       #     #
#     # #  #  # #     #  #####  ######     #####   #     #    #       #    #####   ######
#     # #  #  # #######       # #          #       #     #   #       #     #       #   #
#     # #  #  # #     # #     # #          #       #     #  #       #      #       #    #
#######  ## ##  #     #  #####  #          #        #####  ####### ####### ####### #     #

######  ######  #######
#     # #     # #     #
#     # #     # #     #
######  ######  #     #
#       #   #   #     #
#       #    #  #     #
#       #     # #######

     |----------------------------|
     | OWASP Fuzzer Pro           |
     |----------------------------|
     | OWASP Fuzzing Tool         |
     | Designed by Joseph Craig   |
     |----------------------------|


                                /\\
                               /XX\\
                              /XXXX\\
                             /XXXXXX\\_/\\/\\/\\/\\/\\/\\
                             |XXXXXXXXXXX|           /\\
                             \\XXXXXXXXXXX\\          /XX\\
                               \\XXXXX XXXXXXXXXXXXX XXX\\
                                 \\XXXXXXXXXXXXXXXXXXXX\\
                                  |XXXXXXXXXXXXXXXXXXXX|
                                  \\XXXXXXXXXXXXXXXXXXXX/
                           ________\\XXXXXXXXXXXXXXXXXXX/________
                           \\XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX/
                            \\XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX/
                              ""VXXXXXXXXXXXXXXXXXXXXXV""
                                  ""XXXXXXXXXXXXXV""
                                     ""VXXXXXXXV""
                                        ""VVV""
""")

if __name__ == "__main__":
    print_banner()
    main()
