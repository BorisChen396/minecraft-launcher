import sys, os, json, platform, subprocess, webbrowser, urllib, urllib.request, urllib.parse, re, pathlib

class Auth:
    access_token = ''
    username = None
    uuid = None
    
    def getargs(self) -> list:
        args = [ '--accessToken', self.access_token ]
        if self.username is not None:
            args.extend([ '--username', self.username ])
        if self.uuid is not None:
            args.extend([ '--uuid', self.uuid ])
        return args


def download_file(url, filename) -> None:
    filename = os.path.normpath(filename)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    if os.path.isfile(filename + '.tmp'):
        os.remove(filename + '.tmp')
    if os.path.isfile(filename):
        os.remove(filename)
    urllib.request.urlretrieve(url, filename=filename + '.tmp')
    os.rename(filename + '.tmp', filename)

def request_json(url, headers={}, data=None) -> dict:
    req = urllib.request.Request(url=url, headers=headers, data=data)
    try:
        res = urllib.request.urlopen(req)
        return {
            'code': res.getcode(),
            'content': json.load(res)
        }
    except urllib.request.HTTPError as httpError:
        errorContent = dict({
            'code': httpError.code,
            'reason': httpError.reason
        })
        try:
            errorContent['content'] = json.load(httpError)
        except json.JSONDecodeError:
            pass
        return errorContent

def find_options(regex) -> list:
    return [ arg.split('=', 2).pop() for arg in list(filter(re.compile(regex).match, sys.argv)) ]

def login_ms() -> Auth:
    ms_token_res = None
    ms_token_tmp_path = find_options('--token=.+')[0] if len(find_options('--token=.+')) > 0 else 'refresh_token'
    ms_token_tmp_path = os.path.abspath(os.path.normpath(ms_token_tmp_path))
    if os.path.isfile(ms_token_tmp_path):
        try:
            ms_token_res = request_json('https://login.live.com/oauth20_token.srf', headers={
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data=urllib.parse.urlencode({
                    'client_id': '00000000402b5328',
                    'refresh_token': open(ms_token_tmp_path).read(),
                    'grant_type': 'refresh_token',
                    'redirect_uri': 'https://login.live.com/oauth20_desktop.srf',
                    'scope': 'service::user.auth.xboxlive.com::MBI_SSL'
                }).encode('utf-8'))
            print('Using token file', ms_token_tmp_path)
        except json.JSONDecodeError:
            pass
    if ms_token_res is None:
        ms_login_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402b5328&response_type=code&scope=service%3A%3Auser.auth.xboxlive.com%3A%3AMBI_SSL&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf'
        browser_opened = webbrowser.open(ms_login_url)
        if not browser_opened:
            print('Browse {} to log in with a Microsoft account.'.format(ms_login_url))
        ms_login_redirected_url = None
        while True:
            try:
                ms_login_redirected_url = urllib.parse.urlparse(input('Enter the redirected URL: '))
                if ms_login_redirected_url.hostname == 'login.live.com' and ms_login_redirected_url.path == '/oauth20_desktop.srf':
                    break
                if input('The URL is invalid. Retry? (y/N) ').lower() != 'y':
                    return None
            except EOFError:
                print('Error: STDIN is closed.', file=sys.stderr)
                return None
        
        ms_token_res = request_json('https://login.live.com/oauth20_token.srf',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=urllib.parse.urlencode({
                'client_id': '00000000402b5328',
                'code': dict(urllib.parse.parse_qsl(ms_login_redirected_url.query))['code'],
                'grant_type': 'authorization_code',
                'redirect_uri': 'https://login.live.com/oauth20_desktop.srf',
                'scope': 'service::user.auth.xboxlive.com::MBI_SSL'
            }).encode('utf-8'))
    if ms_token_res['code'] != 200:
        print('Unable to get the access token from Microsoft.', file=sys.stderr)
        print('Server returned with status code {}.'.format(ms_token_res['code']), file=sys.stderr)
        print('Detailed description:', end=' ', file=sys.stderr)
        try:
            print(ms_token_res['content']['error_description'], file=sys.stderr)
        except TypeError:
            print(file=sys.stderr)
        return None
    open(ms_token_tmp_path, mode='w').write(ms_token_res['content']['refresh_token'])
    ms_token = ms_token_res['content']['access_token']
    
    xbl_token_res = request_json('https://user.auth.xboxlive.com/user/authenticate',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }, data=json.dumps({
            'Properties': {
                'AuthMethod': 'RPS',
                'SiteName': 'user.auth.xboxlive.com',
                'RpsTicket': ms_token
            },
            'RelyingParty': 'http://auth.xboxlive.com',
            'TokenType': 'JWT'
        }).encode('utf-8'))
    if xbl_token_res['code'] != 200:
        print('Unable to get the access token from XBox Live.', file=sys.stderr)
        print('Server returned with status code {}.'.format(xbl_token_res['code']), file=sys.stderr)
        return None
    xbl_token = xbl_token_res['content']['Token']

    xsts_token_res = request_json('https://xsts.auth.xboxlive.com/xsts/authorize',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }, data=json.dumps({
            'Properties': {
                'SandboxId': 'RETAIL',
                'UserTokens': [ xbl_token ]
            },
            'RelyingParty': 'rp://api.minecraftservices.com/',
            'TokenType': 'JWT'
        }).encode('utf-8'))
    if xsts_token_res['code'] != 200:
        print('Unable to get the access token from XSTS.', file=sys.stderr)
        print('Server returned with status code {}.'.format(xsts_token_res['code']), file=sys.stderr)
        return None
    xsts_token = xsts_token_res['content']['Token']
    xsts_uhs = xsts_token_res['content']['DisplayClaims']['xui'][0]['uhs']

    mc_token_res = request_json('https://api.minecraftservices.com/authentication/login_with_xbox',
        headers={'Content-Type': 'application/json'}, 
        data=json.dumps({
            'identityToken': 'XBL3.0 x={0};{1}'.format(xsts_uhs, xsts_token)
        }).encode('utf-8'))
    if mc_token_res['code'] != 200:
        print('Unable to get the access token from Minecraft.', file=sys.stderr)
        print('Server returned with status code {}.'.format(mc_token_res['code']), file=sys.stderr)
        print('Detailed description:', end=' ', file=sys.stderr)
        try:
            print(mc_token_res['content']['errorMessage'], file=sys.stderr)
        except TypeError:
            print(file=sys.stderr)
        return None
    mc_token = '{0} {1}'.format(mc_token_res['content']['token_type'], mc_token_res['content']['access_token'])

    mc_profile_res = request_json('https://api.minecraftservices.com/minecraft/profile',
        headers={'Authorization': mc_token})
    if mc_profile_res['code'] != 200:
        print('Unable to get the user profile from Minecraft.', file=sys.stderr)
        print('Server returned with status code {}.'.format(mc_profile_res['code']), file=sys.stderr)
        print('Detailed description:', end=' ', file=sys.stderr)
        try:
            print(mc_profile_res['content']['errorMessage'], file=sys.stderr)
        except TypeError:
            print(file=sys.stderr)
        return None
    
    auth = Auth()
    auth.access_token = mc_token
    auth.username = mc_profile_res['content']['name']
    auth.uuid = mc_profile_res['content']['id']
    return auth

def login_mojang():
    mojang_token_res = request_json('https://authserver.mojang.com/authenticate',
        headers={
            'Content-Type': 'application/json'
        }, data=json.dumps({
            'agent': {
                'name': 'Minecraft',
                'version': 1
            },
            'username': input('Mojang account: '),
            'password': input('Password: ')
        }).encode('utf-8'))
    if mojang_token_res['code'] != 200:
        print('Unable to get the access token from Mojang.', file=sys.stderr)
        print('Server returned with status code {}.'.format(mojang_token_res['code']), file=sys.stderr)
        print('Detailed description:', end=' ', file=sys.stderr)
        try:
            print(mojang_token_res['content']['errorMessage'], file=sys.stderr)
        except TypeError:
            print(file=sys.stderr)
        return None
    
    auth = Auth()
    auth.access_token = mojang_token_res['content']['accessToken']
    auth.username = mojang_token_res['content']['selectedProfile']['name']
    auth.uuid = mojang_token_res['content']['selectedProfile']['id']
    return auth

def check_rules(rules: list) -> bool:
    system_name = platform.system().lower()
    if system_name == 'darwin':
        system_name = 'osx'

    for rule in rules:
        qualified = True if 'os' not in rule else rule['os']['name'] == system_name
        if qualified and rule['action'] == 'disallow':
            return False
        if not qualified and rule['action'] == 'allow':
            return False
    return True

minecraft_path = '.minecraft'
if platform.system().lower() == 'windows':
    minecraft_path = '{0}/.minecraft'.format(os.environ['appdata'])
elif platform.system().lower() == 'linux':
    minecraft_path = '{0}/.minecraft'.format(pathlib.Path.home())
elif platform.system().lower() == 'darwin':
    minecraft_path = '{0}/Library/Application Support/minecraft'.format(pathlib.Path.home())
minecraft_path = os.path.abspath(os.path.normpath(minecraft_path))
print('Minecraft path is set to {}'.format(minecraft_path))

modded_version_manifest = None
if len(find_options('--mod=.+')) > 0:
    modded_version_manifest = json.load(open(os.path.normpath(find_options('--mod=.+')[0])))

print('Obtaining available versions...', end=' ', flush=True)
versions = request_json('https://piston-meta.mojang.com/mc/game/version_manifest.json')
if versions['code'] != 200:
    print('HTTP Error ' + versions['code'], file=sys.stderr)
    raise
print('Done!')
if '--list' in sys.argv:
    print('Available versions:')
    for ver in versions['content']['versions']:
        print(ver['id'])
    exit()

selected_id = ''
if modded_version_manifest is not None:
    selected_id = modded_version_manifest['inheritsFrom']
elif len(find_options('--version=.+')) > 0:
    selected_id = find_options('--version=.+')[0]
else:
    try:
        selected_id = input('Specify a version ID: ')
    except EOFError:
        pass
if selected_id == '':
    selected_id = versions['content']['latest']['release']
possible_versions = [ ver['url'] for ver in versions['content']['versions'] if ver['id'] == selected_id ]
if len(possible_versions) <= 0:
    print('Version "{}" not found.'.format(selected_id), file=sys.stderr)
    raise
version_manifest_url = possible_versions[0]
print('Selected version', selected_id)

print('Obtaining version info...', end=' ', flush=True)
version_manifest_path = '{0}/versions/{1}/{1}.json'.format(minecraft_path, selected_id)
download_file(version_manifest_url, version_manifest_path)
print('Done!')
version_manifest = json.load(open(version_manifest_path))

version_jar_path = '{0}/versions/{1}/{1}.jar'.format(minecraft_path, selected_id)
if os.path.isfile(version_jar_path) == False:
    print('Downloading client JAR...', end=' ', flush=True)
    download_file(version_manifest['downloads']['client']['url'], version_jar_path)
    print('Done!')

libraries = list()
for lib in version_manifest['libraries']:
    if 'rules' in lib and not check_rules(lib['rules']):
        print('Skipping', lib['name'])
        continue
    if 'natives' in lib:
        platform_key = platform.system().lower()
        if platform_key == 'darwin':
            platform_key = 'osx'
        if platform_key not in lib['natives']:
            print('Warning: Natives library "{0}" is unavailable on current platform ({1}).'
                  .format(lib['name'], platform_key))
            continue
        natives_key = lib['natives'][platform_key]
        natives_key = natives_key.replace('${arch}', str('64' if sys.maxsize > 2**32 else '32'))
        if natives_key not in lib['downloads']['classifiers']:
            print('Warning: Natives library "{0}" is unavailable on current platform. ({1})'
                  .format(lib['name'], natives_key))
            continue
        libraries.append({
            'url': lib['downloads']['classifiers'][natives_key]['url'],
            'path': lib['downloads']['classifiers'][natives_key]['path'],
            'natives': True
        })
    else:
        libraries.append({
            'url': lib['downloads']['artifact']['url'],
            'path': lib['downloads']['artifact']['path'],
            'natives': False
        })
if modded_version_manifest is not None:
    for lib in modded_version_manifest['libraries']:
        if 'clientreq' in lib and lib['clientreq'] == False:
            continue
        splited_name = lib['name'].split(':')
        splited_name[0] = splited_name[0].replace('.', '/')
        path = '{0}/{1}/{2}/{1}-{2}.jar'.format(*splited_name)
        libraries.append({
            'url': lib['url'] + path,
            'path': path,
            'natives': False
        })
print('Downloading libraries... (0/{0})'.format(len(libraries)), end='', flush=True)
for lib in libraries:
    path = '{0}/libraries/{1}'.format(minecraft_path, lib['path'])
    if not os.path.isfile(path):
        download_file(lib['url'], path)
    print('\rDownloading libraries... ({0}/{1})'.format(libraries.index(lib) + 1, len(libraries)), end='', flush=True)
print()
natives_libraries = [ lib for lib in libraries if lib['natives'] ]
if len(natives_libraries) > 0:
    print('Extracting natives libraries... (0/{})'.format(len(natives_libraries)), end='', flush=True)
    natives_path = os.path.normpath(minecraft_path + '/natives')
    if not os.path.isdir(natives_path):
        os.makedirs(natives_path)
    for lib in natives_libraries:
        path = '{0}/libraries/{1}'.format(minecraft_path, lib['path'])
        if subprocess.run(['jar', 'xf', path], cwd=natives_path).returncode != 0:
            print('Unable to extract the natives library: {}'.format(lib['name']), file=sys.stderr)
            raise
        print('\rExtracting natives libraries... ({0}/{1})'.format(natives_libraries.index(lib) + 1, len(natives_libraries)), end='', flush=True)
    print()

print('Obtaining assets info...', end=' ', flush=True)
asset_index_path = '{0}/assets/indexes/{1}.json'.format(minecraft_path, version_manifest['assets'])
download_file(version_manifest['assetIndex']['url'], asset_index_path)
print('Done!')
asset_index = json.load(open(asset_index_path))
print('Downloading assets... (0/{0})'.format(len(asset_index['objects'])), end='', flush=True)
for obj in asset_index['objects'].values():
    path = os.path.normpath('{0}/assets/objects/{1}/{2}'.format(minecraft_path, obj['hash'][:2], obj['hash']))
    if os.path.isfile(path) == False:
        download_file('https://resources.download.minecraft.net/{0}/{1}'.format(obj['hash'][:2], obj['hash']), path)
    print('\rDownloading assets... ({0}/{1})'.format(list(asset_index['objects'].values()).index(obj) + 1, len(asset_index['objects'])), end='', flush=True)
print()

classpath = ''
classpath_seperator = ';' if platform.system().lower() == 'windows' else ':'
for lib in libraries:
    if lib['natives']:
        continue
    classpath += os.path.normpath('{0}/libraries/{1}'.format(minecraft_path, lib['path'])) + classpath_seperator
classpath += os.path.normpath(version_jar_path)
custom_classpath = find_options('--classpath=.+')
if len(custom_classpath) > 0:
    classpath += classpath_seperator + custom_classpath[0]

main_class = version_manifest['mainClass']
if modded_version_manifest is not None:
    main_class = modded_version_manifest['mainClass']

game_dir = minecraft_path
if len(find_options('--gameDir=.+')) > 0:
    game_dir = find_options('--gameDir=.+')[0]

java_exec = 'java'
if 'JAVA_HOME' in os.environ: 
    java_exec = os.path.normpath(os.environ['JAVA_HOME'] + '/bin/java')
else:
    print('Warning: JAVA_HOME is not set.')
arguments = [
    java_exec,
    '-cp', classpath,
    '-Djava.library.path={}'.format(os.path.normpath(minecraft_path + '/natives')),
    main_class,
    '--gameDir', game_dir,
    '--assetsDir', os.path.normpath(minecraft_path + '/assets'),
    '--assetIndex', version_manifest['assets'],
    '--version', selected_id, 
    '--userProperties', '{}',
]

auth = None
if '--ms-login' in sys.argv:
    auth = login_ms()
elif '--mojang-login' in sys.argv:
    auth = login_mojang()
if auth is None:
    print('Warning: Not logged in with any account.')
    auth = Auth()
else:
    print('Logged in as {}.'.format(auth.username))
arguments.extend(auth.getargs())

if '--no-launch' in sys.argv:
    exit(0)
else:
    print('Starting Minecraft...')
    exit(subprocess.run(arguments).returncode)