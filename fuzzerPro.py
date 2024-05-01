import sys
import os
import argparse
import subprocess
import requests
import zipfile
import io
import datetime
import platform
from bs4 import BeautifulSoup
from loguru import logger
import tarfile

# Configure logging
logger.add("app.log", rotation="500 MB", level="INFO")


def download_file(url, save_path):
    response = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(response.content)
    logger.info(f"Downloaded file from {url} to {save_path}")


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
    logger.info("SQLMap is already set up.")
    sys.path.append(os.path.abspath('./sqlmap'))


def install_ruby_windows():
    logger.info("Checking for Ruby installation...")
    try:
        ruby_version = subprocess.run(['ruby', '--version'], check=True, capture_output=True, text=True)
        logger.info(f"Ruby is already installed: {ruby_version.stdout.split()[1]}")
    except subprocess.CalledProcessError:
        logger.info("Ruby not found, installing...")
        # Download Ruby Installer
        ruby_installer_url = 'https://github.com/oneclick/rubyinstaller2/releases/latest/download/rubyinstaller-3.1.2-1-x64.exe'
        installer_path = 'rubyinstaller.exe'
        download_file(ruby_installer_url, installer_path)

        # Run the installer
        logger.info("Running Ruby installer, please follow the prompts if any...")
        subprocess.run([installer_path, '/verysilent', '/dir="C:\\Ruby31-x64"'], check=True)
        logger.info("Ruby installed successfully.")
        os.unlink(installer_path)


def setup_cewl():
    os_detected = platform.system()
    if 'cewl' not in subprocess.getoutput('cewl -h'):
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
        logger.info("CEWL downloaded and installed.")
    logger.info("CEWL is already set up.")


def setup_dirbuster():
    os_detected = platform.system()
    dirbuster_dir = None
    try:
        subprocess.run(['dirbuster', '-h'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("DirBuster is already installed.")
        dirbuster_dir = 'dirbuster'  # Assuming it's in the PATH
    except subprocess.CalledProcessError:
        logger.info("DirBuster not found, downloading and installing...")
        dirbuster_zip_url = 'https://sourceforge.net/projects/dirbuster/files/DirBuster%20%28jar%20%2B%20source%29/1.0-RC1/DirBuster-1.0-RC1.tar.bz2/download'
        subprocess.run(['wget', dirbuster_zip_url], check=True)
        subprocess.run(['tar', '-xf', 'download'], check=True)
        dirbuster_dir = os.path.abspath('./DirBuster-1.0-RC1')
        logger.info("DirBuster downloaded and installed.")
    return dirbuster_dir


def install_tools():
    setup_sqlmap()
    setup_cewl()
    setup_dirbuster()
    try:
        from loguru import logger
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


def loop(ip_address, wordlist_file):
    dirbuster_path = setup_dirbuster()
    if dirbuster_path is None:
        logger.error("Failed to set up DirBuster. Exiting.")
        return

    logger.info(f"Scanning target '{ip_address}' with DirBuster...")

    # Run DirBuster
    dirbuster_command = [os.path.join(dirbuster_path, 'dirbuster.sh'), '-H', '-u', f'http://{ip_address}', '-l', wordlist_file, '-t', '50', '-e', 'php,html']
    subprocess.run(dirbuster_command)


#    # Process DirBuster results
#    with open(wordlist_file, 'r') as file:
#        for line in file:
#            directory = line.strip()
#            if os.path.exists(f"DirBuster-1.0-RC1/{directory}/dir-index.html"):
#                url = f"http://{ip_address}/{directory}"
#                try:
#                    inputs = find_input_fields(url)
#                    for input_field in inputs:
#                        input_details = {
#                            "url": url,
#                            "data": f"{input_field['name']}=test"
#                        }
#                        result = send_to_sqlmap(input_details)
#                        if 'success' in result:
#                            logger.info(f"SQL injection successful on {url}")
#                            logger.info("Command executed by SQLMap:")
#                            logger.info(result['command'])
#                        else:
#                            logger.info(f"SQL injection unsuccessful on {url}")
#                except requests.exceptions.JSONDecodeError:
#                    logger.error("Response is not valid JSON.")
#            else:
#                logger.info(f"No valid directories found for '{directory}'.")

def main():
    parser = argparse.ArgumentParser(description='OWASP Fuzzer Pro - A tool for web application security testing.')
    parser.add_argument('-s', help='IP address or website URL of the server to test')
    parser.add_argument('wordlistFileName', nargs='?', help='Filename of the wordlist to use')
    parser.add_argument('-c', help='Generate a wordlist using CEWL for the given IP or website', metavar='TARGET')
    parser.add_argument('-i', '--install', help='Install and setup all necessary tools (SQLMap and CEWL)',
                        action='store_true')

    args = parser.parse_args()

    if args.install:
        install_tools()
    elif args.c:
        setup_cewl()
        wordlist_file = generate_wordlist(args.c)
        loop(args.c, wordlist_file)
    elif args.s and args.wordlistFileName:
        setup_sqlmap()
        loop(args.s, args.wordlistFileName)


if __name__ == "__main__":
    ##print_banner()##
    main()
