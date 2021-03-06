# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.4+ and Openssl 1.0+
#

import socket
import glob
import mock
import azurelinuxagent.common.osutil.default as osutil
import azurelinuxagent.common.utils.shellutil as shellutil
from azurelinuxagent.common.osutil import get_osutil
from tests.tools import *


class TestOSUtil(AgentTestCase):
    def test_restart(self):
        # setup
        retries = 3
        ifname = 'dummy'
        with patch.object(shellutil, "run") as run_patch:
            run_patch.return_value = 1

            # execute
            osutil.DefaultOSUtil.restart_if(osutil.DefaultOSUtil(), ifname=ifname, retries=retries, wait=0)

            # assert
            self.assertEqual(run_patch.call_count, retries)
            self.assertEqual(run_patch.call_args_list[0][0][0], 'ifdown {0} && ifup {0}'.format(ifname))

    def test_get_first_if(self):
        ifname, ipaddr = osutil.DefaultOSUtil().get_first_if()
        self.assertTrue(ifname.startswith('eth'))
        self.assertTrue(ipaddr is not None)
        try:
            socket.inet_aton(ipaddr)
        except socket.error:
            self.fail("not a valid ip address")

    def test_isloopback(self):
        self.assertTrue(osutil.DefaultOSUtil().is_loopback(b'lo'))
        self.assertFalse(osutil.DefaultOSUtil().is_loopback(b'eth0'))

    def test_isprimary(self):
        routing_table = "\
        Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT \n\
        eth0	00000000	01345B0A	0003	0	    0	5	00000000	0	0	0   \n\
        eth0	00345B0A	00000000	0001	0	    0	5	00000000	0	0	0   \n\
        lo	    00000000	01345B0A	0003	0	    0	1	00FCFFFF	0	0	0   \n"

        mo = mock.mock_open(read_data=routing_table)
        with patch(open_patch(), mo):
            self.assertFalse(osutil.DefaultOSUtil().is_primary_interface('lo'))
            self.assertTrue(osutil.DefaultOSUtil().is_primary_interface('eth0'))

    def test_multiple_default_routes(self):
        routing_table = "\
        Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT \n\
        high	00000000	01345B0A	0003	0	    0	5	00000000	0	0	0   \n\
        low1	00000000	01345B0A	0003	0	    0	1	00FCFFFF	0	0	0   \n"

        mo = mock.mock_open(read_data=routing_table)
        with patch(open_patch(), mo):
            self.assertTrue(osutil.DefaultOSUtil().is_primary_interface('low1'))

    def test_multiple_interfaces(self):
        routing_table = "\
        Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT \n\
        first	00000000	01345B0A	0003	0	    0	1	00000000	0	0	0   \n\
        secnd	00000000	01345B0A	0003	0	    0	1	00FCFFFF	0	0	0   \n"

        mo = mock.mock_open(read_data=routing_table)
        with patch(open_patch(), mo):
            self.assertTrue(osutil.DefaultOSUtil().is_primary_interface('first'))

    def test_interface_flags(self):
        routing_table = "\
        Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT \n\
        nflg	00000000	01345B0A	0001	0	    0	1	00000000	0	0	0   \n\
        flgs	00000000	01345B0A	0003	0	    0	1	00FCFFFF	0	0	0   \n"

        mo = mock.mock_open(read_data=routing_table)
        with patch(open_patch(), mo):
            self.assertTrue(osutil.DefaultOSUtil().is_primary_interface('flgs'))

    def test_no_interface(self):
        routing_table = "\
        Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT \n\
        ndst	00000001	01345B0A	0003	0	    0	1	00000000	0	0	0   \n\
        nflg	00000000	01345B0A	0001	0	    0	1	00FCFFFF	0	0	0   \n"

        mo = mock.mock_open(read_data=routing_table)
        with patch(open_patch(), mo):
            self.assertFalse(osutil.DefaultOSUtil().is_primary_interface('ndst'))
            self.assertFalse(osutil.DefaultOSUtil().is_primary_interface('nflg'))
            self.assertFalse(osutil.DefaultOSUtil().is_primary_interface('invalid'))

    def test_no_primary_does_not_throw(self):
        with patch.object(osutil.DefaultOSUtil, 'get_primary_interface') \
                as patch_primary:
            exception = False
            patch_primary.return_value = ''
            try:
                osutil.DefaultOSUtil().get_first_if()[0]
            except Exception as e:
                exception = True
            self.assertFalse(exception)

    def test_dhcp_lease_default(self):
        self.assertTrue(osutil.DefaultOSUtil().get_dhcp_lease_endpoint() is None)

    def test_dhcp_lease_ubuntu(self):
        with patch.object(glob, "glob", return_value=['/var/lib/dhcp/dhclient.eth0.leases']):
            with patch(open_patch(), mock.mock_open(read_data=load_data("dhcp.leases"))):
                endpoint = get_osutil(distro_name='ubuntu', distro_version='12.04').get_dhcp_lease_endpoint()
                self.assertTrue(endpoint is not None)
                self.assertEqual(endpoint, "168.63.129.16")

                endpoint = get_osutil(distro_name='ubuntu', distro_version='12.04').get_dhcp_lease_endpoint()
                self.assertTrue(endpoint is not None)
                self.assertEqual(endpoint, "168.63.129.16")

                endpoint = get_osutil(distro_name='ubuntu', distro_version='14.04').get_dhcp_lease_endpoint()
                self.assertTrue(endpoint is not None)
                self.assertEqual(endpoint, "168.63.129.16")

    def test_dhcp_lease_multi(self):
        with patch.object(glob, "glob", return_value=['/var/lib/dhcp/dhclient.eth0.leases']):
            with patch(open_patch(), mock.mock_open(read_data=load_data("dhcp.leases.multi"))):
                endpoint = get_osutil(distro_name='ubuntu', distro_version='12.04').get_dhcp_lease_endpoint()
                self.assertTrue(endpoint is not None)
                self.assertEqual(endpoint, "second")

if __name__ == '__main__':
    unittest.main()
