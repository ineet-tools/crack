import os
import pathlib
import shutil
from base64 import b64decode, b64encode

from asarPy import extract_asar, pack_asar
from crypto_plus import CryptoPlus
from crypto_plus.encrypt import decrypt_by_key, encrypt_by_key

from crack.base import KeyGen


class XmindKeyGen(KeyGen):

    def __init__(self):
        # tmp_path = os.environ['TMP']
        # mac 软件路径不一样，可以自己看着修改
        asar_path = pathlib.Path('/Applications/Xmind.app/Contents/Resources')
        self.asar_file = asar_path.joinpath('app.asar')
        self.asar_file_bak = asar_path.joinpath('app.asar.bak')
        self.crack_asar_dir = asar_path.joinpath('ext')
        self.main_dir = self.crack_asar_dir.joinpath("main")
        self.renderer_dir = self.crack_asar_dir.joinpath("renderer")
        self.private_key = None
        self.public_key = None
        self.old_public_key = open('old.pem').read()

    def generate(self):
        if os.path.isfile('key.pem'):
            rsa = CryptoPlus.load('key.pem')
        else:
            rsa = CryptoPlus.generate_rsa(1024)
            rsa.dump("key.pem", "new_public_key.pem")
        license_info = '{"status": "sub", "expireTime": 4093057076000, "ss": "", "deviceId": "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"}'
        self.public_key = rsa.public_key
        self.private_key = rsa.private_key
        self.license_data = b64encode(encrypt_by_key(rsa.private_key, license_info.encode()))
        return self.license_data

    def parse(self, licenses):
        return decrypt_by_key(self.public_key, b64decode(licenses))

    def patch(self):
        # 先删除接包的内容，防止已经存在报错
        # shutil.rmtree(self.crack_asar_dir)
        # 解包
        extract_asar(str(self.asar_file), str(self.crack_asar_dir))
        shutil.copytree('crack', self.main_dir, dirs_exist_ok=True)
        # 注入
        # 看了一下mac最新版本的源代码只有一行，这里采用插入首行
        with open(self.main_dir.joinpath('main.js'), 'rb') as f:
            lines = f.readlines()
            # lines[5] = b'require("./hook")\n'
        lines.insert(0, b'require("./hook");\n')
        with open(self.main_dir.joinpath('main.js'), 'wb') as f:
            f.writelines(lines)
        # 替换密钥
        old_key = f"String.fromCharCode({','.join([str(i) for i in self.old_public_key.encode()])})".encode()
        new_key = f"String.fromCharCode({','.join([str(i) for i in self.public_key.export_key()])})".encode()
        for js_file in self.renderer_dir.rglob("*.js"):
            with open(js_file, 'rb') as f:
                byte_str = f.read()
                index = byte_str.find(old_key)
                if index != -1:
                    byte_str.replace(old_key, new_key)
                    with open(js_file, 'wb') as _f:
                        _f.write(byte_str.replace(old_key, new_key))
                    print(js_file)
                    break
        # 手动搜索发现 main.js 里面也有公钥信息，一起替换掉
        for js_file in self.main_dir.rglob("*.js"):
            with open(js_file, 'rb') as f:
                byte_str = f.read()
                index = byte_str.find(old_key)
                if index != -1:
                    byte_str.replace(old_key, new_key)
                    with open(js_file, 'wb') as _f:
                        _f.write(byte_str.replace(old_key, new_key))
                    print(js_file)
                    break
        # 占位符填充
        with open(self.main_dir.joinpath('hook.js'), 'r', encoding='u8') as f:
            content = f.read()
            content = content.replace("{{license_data}}", self.license_data.decode())
        with open(self.main_dir.joinpath('hook.js'), 'w', encoding='u8') as f:
            f.write(content)
        with open(self.main_dir.joinpath('hook').joinpath('crypto.js'), 'r', encoding='u8') as f:
            content = f.read()
            content = content.replace("{{old_public_key}}", self.old_public_key.replace("\n", "\\n"))
            content = content.replace("{{new_public_key}}", self.public_key.export_key().decode().replace("\n", "\\n"))
        with open(self.main_dir.joinpath('hook').joinpath('crypto.js'), 'w', encoding='u8') as f:
            f.write(content)
        # 封包
        os.remove(self.asar_file)
        pack_asar(self.crack_asar_dir, self.asar_file)
        shutil.rmtree(self.crack_asar_dir)


if __name__ == '__main__':
    XmindKeyGen().run()