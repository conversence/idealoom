from builtins import object
import re
from os import urandom
from abc import abstractmethod
from base64 import urlsafe_b64encode, urlsafe_b64decode


class Obfuscator(object):
    @abstractmethod
    def encrypt(self, text):
        pass

    @abstractmethod
    def decrypt(self, code):
        pass

    type_names = "(?:/data/|local:)"\
        "(?:Agent|UserAccount|AgentProfile|AgentAccount|AbstractAgentAccount)"
    obfuscate_re = re.compile(r'(%s/)(\d+)\b' % (type_names,))
    deobfuscate_re = re.compile(r'(%s(?:\\?)/)([-=\w]+)' % (type_names,))

    def obfuscate(self, serialized_rdf, obfuscator=None):
        # Work in progress.
        return self.obfuscate_re.sub(lambda matchob: (
            matchob.group(1) + self.encrypt(matchob.group(2))), serialized_rdf)

    def deobfuscate(self, serialized_rdf):
        # Work in progress.
        return self.deobfuscate_re.sub(lambda matchob: (
            matchob.group(1) + self.decrypt(matchob.group(2))), serialized_rdf)


class AESObfuscator(Obfuscator):
    def __init__(self, key=None, blocklen=16):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        key = key or urandom(blocklen)
        iv = b' ' * blocklen
        self.blocklen = blocklen
        self.cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())

    def encrypt(self, text):
        text = text.encode('utf-8')
        encryptor = self.cipher.encryptor()
        return urlsafe_b64encode(encryptor.update(text) + encryptor.finalize()).decode('iso-8859-1')

    def decrypt(self, code):
        decryptor = self.cipher.decryptor()
        code = code.encode('iso-8859-1')
        text = decryptor.update(urlsafe_b64decode(code)) + decryptor.finalize()
        return text.decode('utf-8')

    def pad(self, key, blocklen=None, padding=b' '):
        blocklen = blocklen or self.blocklen
        return key + padding * (blocklen - (len(key) % blocklen))
