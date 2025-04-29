import unittest
from mock import patch

from app import (app, r)

pxe_default = '''default local
prompt 0
timeout 0
label local
    localboot 0'''

pxe_boot = '''default linux
prompt 0
timeout 100
label linux
    kernel path/to/kernel
    ipappend 2
    append initrd=path/to/initrd  netboot_method=pxe'''

grub2_default = '''exit'''

grub2_boot = '''linuxefi  path/to/kernel  netboot_method=grub2
initrdefi path/to/initrd

boot'''

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        self.client = app.test_client()

    def tearDown(self):
        self.ctx.pop()

    @patch.object(r, 'hgetall')
    def test_netboot_default_pxe(self, mock_redis):
        response = self.client.get("/netboots/0A3C0034/pxe")
        assert response.status_code == 200
        assert response.data.decode() == pxe_default

    @patch.object(r, 'hgetall')
    @patch.object(r, 'expire')
    def test_netboot_boot_pxe(self, mock_redis_obj1, mock_redis_obj2):
        mock_redis_obj2.return_value = {"hex_ip".encode(): "0A3C0034".encode(),
                                   "kernel_path".encode(): "path/to/kernel".encode(),
                                   "initrd_path".encode(): "path/to/initrd".encode()}
        response = self.client.get("/netboots/0A3C0034/pxe")
        assert response.status_code == 200
        assert response.data.decode() == pxe_boot

    @patch.object(r, 'hgetall')
    def test_netboot_default_grub2(self, mock_redis):
        response = self.client.get("/netboots/0A3C0034/grub2")
        assert response.status_code == 200
        assert response.data.decode() == grub2_default

    @patch.object(r, 'hgetall')
    @patch.object(r, 'expire')
    def test_netboot_boot_grub2(self, mock_redis_obj1, mock_redis_obj2):
        mock_redis_obj2.return_value = {"hex_ip".encode(): "0A3C0034".encode(),
                                   "kernel_path".encode(): "path/to/kernel".encode(),
                                   "initrd_path".encode(): "path/to/initrd".encode()}
        response = self.client.get("/netboots/0A3C0034/grub2")
        assert response.status_code == 200
        assert response.data.decode() == grub2_boot

if __name__ == "__main__":
    unittest.main()
