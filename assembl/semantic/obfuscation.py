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

    def obfuscate(self, serialized_rdf, obfuscator=None):
        # Work in progress.
        r = re.compile(r'((?:/data/|local:)(?:AgentProfile|AgentAccount|AbstractAgentAccount)/)(\d+)\b')
        return r.sub(lambda matchob: (
            matchob.group(1) + self.encrypt(matchob.group(2))), serialized_rdf)

    def deobfuscate(self, serialized_rdf):
        # Work in progress.
        r = re.compile(r'((?:/data/|local:)(?:AgentProfile|AgentAccount|AbstractAgentAccount)(?:\\?)/)([-=\w]+)')
        return r.sub(lambda matchob: (
            matchob.group(1) + self.decrypt(matchob.group(2))), serialized_rdf)


class AESObfuscator(Obfuscator):
    def __init__(self, key=None, blocklen=16):
        key = key or urandom(blocklen)
        self.key = self.pad(key, blocklen)
        self.blocklen = blocklen
        self.IV = ' ' * blocklen

    def encrypt(self, text):
        from Crypto.Cipher import AES
        encoder = AES.new(self.key, AES.MODE_CFB, self.IV)
        return urlsafe_b64encode(encoder.encrypt(text))

    def decrypt(self, code):
        from Crypto.Cipher import AES
        encoder = AES.new(self.key, AES.MODE_CFB, self.IV)
        code = code.encode('utf-8')
        code = urlsafe_b64decode(code)
        return encoder.decrypt(code)

    def pad(self, key, blocklen=16, padding=' '):
        return key + padding * (blocklen - (len(key) % blocklen))
