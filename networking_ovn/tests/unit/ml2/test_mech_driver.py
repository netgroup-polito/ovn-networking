#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import mock
from webob import exc

from neutron_lib import constants as const
from neutron_lib import exceptions as n_exc
from oslo_db import exception as os_db_exc

from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources
from neutron.common import utils as n_utils
from neutron.db import provisioning_blocks
from neutron.extensions import portbindings
from neutron import manager
from neutron.plugins.ml2 import config
from neutron.plugins.ml2.drivers import type_geneve  # noqa
from neutron.tests import tools
from neutron.tests.unit.extensions import test_segment
from neutron.tests.unit.plugins.ml2 import test_ext_portsecurity
from neutron.tests.unit.plugins.ml2 import test_plugin

from networking_ovn.common import acl as ovn_acl
from networking_ovn.common import constants as ovn_const
from networking_ovn.common import utils as ovn_utils
from networking_ovn.tests.unit import fakes


class TestOVNMechanismDriver(test_plugin.Ml2PluginV2TestCase):

    _mechanism_drivers = ['logger', 'ovn']
    _extension_drivers = ['port_security']

    def setUp(self):
        config.cfg.CONF.set_override('extension_drivers',
                                     self._extension_drivers,
                                     group='ml2')
        config.cfg.CONF.set_override('tenant_network_types',
                                     ['geneve'],
                                     group='ml2')
        config.cfg.CONF.set_override('vni_ranges',
                                     ['1:65536'],
                                     group='ml2_type_geneve')
        super(TestOVNMechanismDriver, self).setUp()
        mm = manager.NeutronManager.get_plugin().mechanism_manager
        self.mech_driver = mm.mech_drivers['ovn'].obj
        self.mech_driver._nb_ovn = fakes.FakeOvsdbNbOvnIdl()
        self.mech_driver._sb_ovn = fakes.FakeOvsdbSbOvnIdl()
        self.nb_ovn = self.mech_driver._nb_ovn
        self.sb_ovn = self.mech_driver._sb_ovn

        self.fake_subnet = fakes.FakeSubnet.create_one_subnet().info()
        self.fake_port_no_sg = fakes.FakePort.create_one_port().info()

        self.fake_sg_rule = \
            fakes.FakeSecurityGroupRule.create_one_security_group_rule().info()
        self.fake_sg = fakes.FakeSecurityGroup.create_one_security_group(
            attrs={'security_group_rules': [self.fake_sg_rule]}
        ).info()

        self.sg_cache = {self.fake_sg['id']: self.fake_sg}
        self.subnet_cache = {self.fake_subnet['id']: self.fake_subnet}

    def test__process_sg_notification_create(self):
        self.mech_driver._process_sg_notification(
            resources.SECURITY_GROUP, events.AFTER_CREATE, {},
            security_group=self.fake_sg)
        external_ids = {ovn_const.OVN_SG_NAME_EXT_ID_KEY: self.fake_sg['name']}
        ip4_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip4')
        ip6_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip6')
        create_address_set_calls = [mock.call(name=name,
                                              external_ids=external_ids)
                                    for name in [ip4_name, ip6_name]]

        self.nb_ovn.create_address_set.assert_has_calls(
            create_address_set_calls, any_order=True)

    def test__process_sg_notification_update(self):
        self.mech_driver._process_sg_notification(
            resources.SECURITY_GROUP, events.AFTER_UPDATE, {},
            security_group=self.fake_sg)
        external_ids = {ovn_const.OVN_SG_NAME_EXT_ID_KEY: self.fake_sg['name']}
        ip4_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip4')
        ip6_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip6')
        update_address_set_calls = [mock.call(name=name,
                                              external_ids=external_ids)
                                    for name in [ip4_name, ip6_name]]

        self.nb_ovn.update_address_set_ext_ids.assert_has_calls(
            update_address_set_calls, any_order=True)

    def test__process_sg_notification_delete(self):
        self.mech_driver._process_sg_notification(
            resources.SECURITY_GROUP, events.BEFORE_DELETE, {},
            security_group=self.fake_sg)
        ip4_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip4')
        ip6_name = ovn_utils.ovn_addrset_name(self.fake_sg['id'], 'ip6')
        delete_address_set_calls = [mock.call(name=name)
                                    for name in [ip4_name, ip6_name]]

        self.nb_ovn.delete_address_set.assert_has_calls(
            delete_address_set_calls, any_order=True)

    def test__process_sg_rule_notifications_sgr_create(self):
        with mock.patch(
            'networking_ovn.common.acl.update_acls_for_security_group'
        ) as ovn_acl_up:
            rule = {'security_group_id': 'sg_id'}
            self.mech_driver._process_sg_rule_notification(
                resources.SECURITY_GROUP_RULE, events.AFTER_CREATE, {},
                security_group_rule=rule)
            ovn_acl_up.assert_called_once_with(
                mock.ANY, mock.ANY, mock.ANY,
                'sg_id', rule, is_add_acl=True)

    def test_process_sg_rule_notifications_sgr_delete(self):
        rule = {'security_group_id': 'sg_id'}
        with mock.patch(
            'networking_ovn.common.acl.update_acls_for_security_group'
        ) as ovn_acl_up:
            with mock.patch(
                'neutron.db.securitygroups_db.'
                'SecurityGroupDbMixin.get_security_group_rule',
                return_value=rule
            ):
                self.mech_driver._process_sg_rule_notification(
                    resources.SECURITY_GROUP_RULE, events.BEFORE_DELETE, {},
                    security_group_rule=rule)
                ovn_acl_up.assert_called_once_with(
                    mock.ANY, mock.ANY, mock.ANY,
                    'sg_id', rule, is_add_acl=False)

    def test_add_acls_no_sec_group(self):
        acls = ovn_acl.add_acls(self.mech_driver._plugin,
                                mock.Mock(),
                                self.fake_port_no_sg,
                                {}, {})
        self.assertEqual([], acls)

    def _test_add_acls_with_sec_group_helper(self, native_dhcp=True):
        fake_port_sg = fakes.FakePort.create_one_port(
            attrs={'security_groups': [self.fake_sg['id']],
                   'fixed_ips': [{'subnet_id': self.fake_subnet['id'],
                                  'ip_address': '10.10.10.20'}]}
        ).info()

        expected_acls = []
        expected_acls += ovn_acl.drop_all_ip_traffic_for_port(
            fake_port_sg)
        if not native_dhcp:
            expected_acls += ovn_acl.add_acl_dhcp(
                fake_port_sg, self.fake_subnet)
        sg_rule_acl = ovn_acl.add_sg_rule_acl_for_port(
            fake_port_sg, self.fake_sg_rule,
            'outport == "' + fake_port_sg['id'] + '" ' +
            '&& ip4 && ip4.src == 0.0.0.0/0 ' +
            '&& tcp && tcp.dst == 22')
        expected_acls.append(sg_rule_acl)

        # Test with caches
        acls = ovn_acl.add_acls(self.mech_driver._plugin,
                                mock.Mock(),
                                fake_port_sg,
                                self.sg_cache,
                                self.subnet_cache)
        self.assertEqual(expected_acls, acls)

        # Test without caches
        with mock.patch('neutron.db.db_base_plugin_v2.'
                        'NeutronDbPluginV2.get_subnet',
                        return_value=self.fake_subnet), \
            mock.patch('neutron.db.securitygroups_db.'
                       'SecurityGroupDbMixin.get_security_group',
                       return_value=self.fake_sg):

            acls = ovn_acl.add_acls(self.mech_driver._plugin,
                                    mock.Mock(),
                                    fake_port_sg,
                                    {}, {})
            self.assertEqual(expected_acls, acls)

        # Test with security groups disabled
        with mock.patch('networking_ovn.common.acl.is_sg_enabled',
                        return_value=False):
            acls = ovn_acl.add_acls(self.mech_driver._plugin,
                                    mock.Mock(),
                                    fake_port_sg,
                                    self.sg_cache,
                                    self.subnet_cache)
            self.assertEqual([], acls)

        # Test with multiple fixed IPs on the same subnet.
        fake_port_sg['fixed_ips'].append({'subnet_id': self.fake_subnet['id'],
                                          'ip_address': '10.10.10.21'})
        acls = ovn_acl.add_acls(self.mech_driver._plugin,
                                mock.Mock(),
                                fake_port_sg,
                                self.sg_cache,
                                self.subnet_cache)
        self.assertEqual(expected_acls, acls)

    def test_add_acls_with_sec_group_native_dhcp_enabled(self):
        self._test_add_acls_with_sec_group_helper()

    def test_add_acls_with_sec_group_native_dhcp_disabled(self):
        config.cfg.CONF.set_override('ovn_native_dhcp',
                                     False,
                                     group='ovn')
        self._test_add_acls_with_sec_group_helper(native_dhcp=False)

    def test_port_invalid_binding_profile(self):
        invalid_binding_profiles = [
            {'tag': 0,
             'parent_name': 'fakename'},
            {'tag': 1024},
            {'tag': 1024, 'parent_name': 1024},
            {'parent_name': 'test'},
            {'tag': 'test'},
            {'vtep-physical-switch': 'psw1'},
            {'vtep-logical-switch': 'lsw1'},
            {'vtep-physical-switch': 'psw1', 'vtep-logical-switch': 1234},
            {'vtep-physical-switch': 1234, 'vtep-logical-switch': 'lsw1'},
            {'vtep-physical-switch': 'psw1', 'vtep-logical-switch': 'lsw1',
             'tag': 1024},
            {'vtep-physical-switch': 'psw1', 'vtep-logical-switch': 'lsw1',
             'parent_name': 'fakename'},
            {'vtep-physical-switch': 'psw1', 'vtep-logical-switch': 'lsw1',
             'tag': 1024, 'parent_name': 'fakename'},
        ]
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                # succeed without binding:profile
                with self.port(subnet=subnet1,
                               set_context=True, tenant_id='test'):
                    pass
                # fail with invalid binding profiles
                for invalid_profile in invalid_binding_profiles:
                    try:
                        kwargs = {ovn_const.OVN_PORT_BINDING_PROFILE:
                                  invalid_profile}
                        with self.port(
                                subnet=subnet1,
                                expected_res_status=403,
                                arg_list=(
                                ovn_const.OVN_PORT_BINDING_PROFILE,),
                                set_context=True, tenant_id='test',
                                **kwargs):
                            pass
                    except exc.HTTPClientError:
                        pass

    def test_create_port_security(self):
        kwargs = {'mac_address': '00:00:00:00:00:01',
                  'fixed_ips': [{'ip_address': '10.0.0.2'},
                                {'ip_address': '10.0.0.4'}]}
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               arg_list=('mac_address', 'fixed_ips'),
                               set_context=True, tenant_id='test',
                               **kwargs) as port:
                    self.assertTrue(self.nb_ovn.create_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.create_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual(['00:00:00:00:00:01 10.0.0.2 10.0.0.4'],
                                     called_args_dict.get('port_security'))

                    data = {'port': {'mac_address': '00:00:00:00:00:02'}}
                    req = self.new_update_request(
                        'ports',
                        data, port['port']['id'])
                    req.get_response(self.api)
                    self.assertTrue(self.nb_ovn.set_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.set_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual(['00:00:00:00:00:02 10.0.0.2 10.0.0.4'],
                                     called_args_dict.get('port_security'))

    def test_create_port_with_disabled_security(self):
        kwargs = {'port_security_enabled': False}
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               arg_list=('port_security_enabled',),
                               set_context=True, tenant_id='test',
                               **kwargs) as port:
                    self.assertTrue(self.nb_ovn.create_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.create_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual([],
                                     called_args_dict.get('port_security'))

                    data = {'port': {'mac_address': '00:00:00:00:00:01'}}
                    req = self.new_update_request(
                        'ports',
                        data, port['port']['id'])
                    req.get_response(self.api)
                    self.assertTrue(self.nb_ovn.set_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.set_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual([],
                                     called_args_dict.get('port_security'))

    def test_create_port_security_allowed_address_pairs(self):
        kwargs = {'allowed_address_pairs':
                  [{"ip_address": "1.1.1.1"},
                   {"ip_address": "2.2.2.2",
                    "mac_address": "22:22:22:22:22:22"}]}
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               arg_list=('allowed_address_pairs',),
                               set_context=True, tenant_id='test',
                               **kwargs) as port:
                    port_ip = port['port'].get('fixed_ips')[0]['ip_address']
                    self.assertTrue(self.nb_ovn.create_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.create_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual(
                        tools.UnorderedList(
                            ["22:22:22:22:22:22 2.2.2.2",
                             port['port']['mac_address'] + ' ' + port_ip
                             + ' ' + '1.1.1.1']),
                        called_args_dict.get('port_security'))

                    old_mac = port['port']['mac_address']

                    # we are updating only the port mac address. So the
                    # mac address of the allowed address pair ip 1.1.1.1
                    # will have old mac address
                    data = {'port': {'mac_address': '00:00:00:00:00:01'}}
                    req = self.new_update_request(
                        'ports',
                        data, port['port']['id'])
                    req.get_response(self.api)
                    self.assertTrue(self.nb_ovn.set_lswitch_port.called)
                    called_args_dict = (
                        (self.nb_ovn.set_lswitch_port
                         ).call_args_list[0][1])
                    self.assertEqual(tools.UnorderedList(
                        ["22:22:22:22:22:22 2.2.2.2",
                         "00:00:00:00:00:01 " + port_ip,
                         old_mac + " 1.1.1.1"]),
                        called_args_dict.get('port_security'))

    def _create_fake_network_context(self,
                                     network_type,
                                     physical_network=None,
                                     segmentation_id=None):
        network_attrs = {'provider:network_type': network_type,
                         'provider:physical_network': physical_network,
                         'provider:segmentation_id': segmentation_id}
        segment_attrs = {'network_type': network_type,
                         'physical_network': physical_network,
                         'segmentation_id': segmentation_id}
        fake_network = \
            fakes.FakeNetwork.create_one_network(attrs=network_attrs).info()
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        return fakes.FakeNetworkContext(fake_network, fake_segments)

    def _create_fake_mp_network_context(self):
        network_type = 'flat'
        network_attrs = {'segments': []}
        fake_segments = []
        for physical_network in ['physnet1', 'physnet2']:
            network_attrs['segments'].append(
                {'provider:network_type': network_type,
                 'provider:physical_network': physical_network})
            segment_attrs = {'network_type': network_type,
                             'physical_network': physical_network}
            fake_segments.append(
                fakes.FakeSegment.create_one_segment(
                    attrs=segment_attrs).info())
        fake_network = \
            fakes.FakeNetwork.create_one_network(attrs=network_attrs).info()
        fake_network.pop('provider:network_type')
        fake_network.pop('provider:physical_network')
        fake_network.pop('provider:segmentation_id')
        return fakes.FakeNetworkContext(fake_network, fake_segments)

    def test_network_precommit(self):
        # Test supported network types.
        fake_network_context = self._create_fake_network_context('local')
        self.mech_driver.create_network_precommit(fake_network_context)
        fake_network_context = self._create_fake_network_context(
            'flat', physical_network='physnet')
        self.mech_driver.update_network_precommit(fake_network_context)
        fake_network_context = self._create_fake_network_context(
            'geneve', segmentation_id=10)
        self.mech_driver.create_network_precommit(fake_network_context)
        fake_network_context = self._create_fake_network_context(
            'vlan', physical_network='physnet', segmentation_id=11)
        self.mech_driver.update_network_precommit(fake_network_context)
        fake_mp_network_context = self._create_fake_mp_network_context()
        self.mech_driver.create_network_precommit(fake_mp_network_context)

        # Test unsupported network types.
        fake_network_context = self._create_fake_network_context(
            'vxlan', segmentation_id=12)
        self.assertRaises(n_exc.InvalidInput,
                          self.mech_driver.create_network_precommit,
                          fake_network_context)
        fake_network_context = self._create_fake_network_context(
            'gre', segmentation_id=13)
        self.assertRaises(n_exc.InvalidInput,
                          self.mech_driver.update_network_precommit,
                          fake_network_context)

    def test_create_port_without_security_groups(self):
        kwargs = {'security_groups': []}
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               arg_list=('security_groups',),
                               set_context=True, tenant_id='test',
                               **kwargs):
                    self.assertEqual(
                        1, self.nb_ovn.create_lswitch_port.call_count)
                    self.nb_ovn.add_acl.assert_not_called()
                    self.nb_ovn.update_address_set.assert_not_called()

    def _test_create_port_with_security_groups_helper(self,
                                                      add_acl_call_count):
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               set_context=True, tenant_id='test'):
                    self.assertEqual(
                        1, self.nb_ovn.create_lswitch_port.call_count)
                    self.assertEqual(
                        add_acl_call_count, self.nb_ovn.add_acl.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_address_set.call_count)

    def test_create_port_with_security_groups_native_dhcp_enabled(self):
        self._test_create_port_with_security_groups_helper(6)

    def test_create_port_with_security_groups_native_dhcp_disabled(self):
        config.cfg.CONF.set_override('ovn_native_dhcp',
                                     False,
                                     group='ovn')
        self._test_create_port_with_security_groups_helper(8)

    def test_update_port_changed_security_groups(self):
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               set_context=True, tenant_id='test') as port1:
                    sg_id = port1['port']['security_groups'][0]

                    # Remove the default security group.
                    self.nb_ovn.set_lswitch_port.reset_mock()
                    self.nb_ovn.update_acls.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    data = {'port': {'security_groups': []}}
                    self._update('ports', port1['port']['id'], data)
                    self.assertEqual(
                        1, self.nb_ovn.set_lswitch_port.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_acls.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_address_set.call_count)

                    # Add the default security group.
                    self.nb_ovn.set_lswitch_port.reset_mock()
                    self.nb_ovn.update_acls.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    data = {'port': {'security_groups': [sg_id]}}
                    self._update('ports', port1['port']['id'], data)
                    self.assertEqual(
                        1, self.nb_ovn.set_lswitch_port.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_acls.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_address_set.call_count)

    def test_update_port_unchanged_security_groups(self):
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               set_context=True, tenant_id='test') as port1:
                    # Update the port name.
                    self.nb_ovn.set_lswitch_port.reset_mock()
                    self.nb_ovn.update_acls.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    data = {'port': {'name': 'rtheis'}}
                    self._update('ports', port1['port']['id'], data)
                    self.assertEqual(
                        1, self.nb_ovn.set_lswitch_port.call_count)
                    self.nb_ovn.update_acls.assert_not_called()
                    self.nb_ovn.update_address_set.assert_not_called()

                    # Update the port fixed IPs
                    self.nb_ovn.set_lswitch_port.reset_mock()
                    self.nb_ovn.update_acls.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    data = {'port': {'fixed_ips': []}}
                    self._update('ports', port1['port']['id'], data)
                    self.assertEqual(
                        1, self.nb_ovn.set_lswitch_port.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_acls.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_address_set.call_count)

    def test_delete_port_without_security_groups(self):
        kwargs = {'security_groups': []}
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               arg_list=('security_groups',),
                               set_context=True, tenant_id='test',
                               **kwargs) as port1:
                    self.nb_ovn.delete_lswitch_port.reset_mock()
                    self.nb_ovn.delete_acl.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    self._delete('ports', port1['port']['id'])
                    self.assertEqual(
                        1, self.nb_ovn.delete_lswitch_port.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.delete_acl.call_count)
                    self.nb_ovn.update_address_set.assert_not_called()

    def test_delete_port_with_security_groups(self):
        with self.network(set_context=True, tenant_id='test') as net1:
            with self.subnet(network=net1) as subnet1:
                with self.port(subnet=subnet1,
                               set_context=True, tenant_id='test') as port1:
                    self.nb_ovn.delete_lswitch_port.reset_mock()
                    self.nb_ovn.delete_acl.reset_mock()
                    self.nb_ovn.update_address_set.reset_mock()
                    self._delete('ports', port1['port']['id'])
                    self.assertEqual(
                        1, self.nb_ovn.delete_lswitch_port.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.delete_acl.call_count)
                    self.assertEqual(
                        1, self.nb_ovn.update_address_set.call_count)

    def test_set_port_status_up(self):
        with self.network(set_context=True, tenant_id='test') as net1, \
            self.subnet(network=net1) as subnet1, \
            self.port(subnet=subnet1, set_context=True,
                      tenant_id='test') as port1, \
            mock.patch('neutron.db.provisioning_blocks.'
                       'provisioning_complete') as pc:
                self.mech_driver.set_port_status_up(port1['port']['id'])
                pc.assert_called_once_with(
                    mock.ANY,
                    port1['port']['id'],
                    resources.PORT,
                    provisioning_blocks.L2_AGENT_ENTITY
                )

    def test_set_port_status_down(self):
        with self.network(set_context=True, tenant_id='test') as net1, \
            self.subnet(network=net1) as subnet1, \
            self.port(subnet=subnet1, set_context=True,
                      tenant_id='test') as port1, \
            mock.patch('neutron.db.provisioning_blocks.'
                       'add_provisioning_component') as apc:
                self.mech_driver.set_port_status_down(port1['port']['id'])
                apc.assert_called_once_with(
                    mock.ANY,
                    port1['port']['id'],
                    resources.PORT,
                    provisioning_blocks.L2_AGENT_ENTITY
                )

    def test_set_port_status_down_not_found(self):
        with mock.patch('neutron.db.provisioning_blocks.'
                        'add_provisioning_component') as apc:
            self.mech_driver.set_port_status_down('foo')
            apc.assert_not_called()

    def test_set_port_status_concurrent_delete(self):
        exc = os_db_exc.DBReferenceError('', '', '', '')
        with self.network(set_context=True, tenant_id='test') as net1, \
            self.subnet(network=net1) as subnet1, \
            self.port(subnet=subnet1, set_context=True,
                      tenant_id='test') as port1, \
            mock.patch('neutron.db.provisioning_blocks.'
                       'add_provisioning_component',
                       side_effect=exc) as apc:
                self.mech_driver.set_port_status_down(port1['port']['id'])
                apc.assert_called_once_with(
                    mock.ANY,
                    port1['port']['id'],
                    resources.PORT,
                    provisioning_blocks.L2_AGENT_ENTITY
                )

    def test_bind_port_unsupported_vnic_type(self):
        fake_port = fakes.FakePort.create_one_port(
            attrs={'binding:vnic_type': 'unknown'}).info()
        fake_port_context = fakes.FakePortContext(fake_port, 'host', [])
        self.mech_driver.bind_port(fake_port_context)
        self.sb_ovn.get_chassis_data_for_ml2_bind_port.assert_not_called()
        fake_port_context.set_binding.assert_not_called()

    def _test_bind_port_failed(self, fake_segments):
        fake_port = fakes.FakePort.create_one_port().info()
        fake_host = 'host'
        fake_port_context = fakes.FakePortContext(
            fake_port, fake_host, fake_segments)
        self.mech_driver.bind_port(fake_port_context)
        self.sb_ovn.get_chassis_data_for_ml2_bind_port.assert_called_once_with(
            fake_host)
        fake_port_context.set_binding.assert_not_called()

    def test_bind_port_host_not_found(self):
        self.sb_ovn.get_chassis_data_for_ml2_bind_port.side_effect = \
            RuntimeError
        self._test_bind_port_failed([])

    def test_bind_port_no_segments_to_bind(self):
        self._test_bind_port_failed([])

    def test_bind_port_physnet_not_found(self):
        segment_attrs = {'network_type': 'vlan',
                         'physical_network': 'unknown-physnet',
                         'segmentation_id': 23}
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        self._test_bind_port_failed(fake_segments)

    def _test_bind_port(self, fake_segments):
        fake_port = fakes.FakePort.create_one_port().info()
        fake_host = 'host'
        fake_port_context = fakes.FakePortContext(
            fake_port, fake_host, fake_segments)
        self.mech_driver.bind_port(fake_port_context)
        self.sb_ovn.get_chassis_data_for_ml2_bind_port.assert_called_once_with(
            fake_host)
        fake_port_context.set_binding.assert_called_once_with(
            fake_segments[0]['id'],
            portbindings.VIF_TYPE_OVS,
            self.mech_driver.vif_details[portbindings.VIF_TYPE_OVS])

    def test_bind_port_geneve(self):
        segment_attrs = {'network_type': 'geneve',
                         'physical_network': None,
                         'segmentation_id': 1023}
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        self._test_bind_port(fake_segments)

    def test_bind_port_vlan(self):
        segment_attrs = {'network_type': 'vlan',
                         'physical_network': 'fake-physnet',
                         'segmentation_id': 23}
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        self._test_bind_port(fake_segments)

    def test_bind_port_flat(self):
        segment_attrs = {'network_type': 'flat',
                         'physical_network': 'fake-physnet',
                         'segmentation_id': None}
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        self._test_bind_port(fake_segments)

    def test_bind_port_vxlan(self):
        segment_attrs = {'network_type': 'vxlan',
                         'physical_network': None,
                         'segmentation_id': 1024}
        fake_segments = \
            [fakes.FakeSegment.create_one_segment(attrs=segment_attrs).info()]
        self._test_bind_port(fake_segments)

    def test__is_port_provisioning_required(self):
        fake_port = fakes.FakePort.create_one_port(
            attrs={'binding:vnic_type': 'normal',
                   'status': const.PORT_STATUS_DOWN}).info()
        fake_host = 'fake-physnet'

        # Test host not changed
        self.assertFalse(self.mech_driver._is_port_provisioning_required(
            fake_port, fake_host, fake_host))

        # Test invalid vnic type.
        fake_port['binding:vnic_type'] = 'unknown'
        self.assertFalse(self.mech_driver._is_port_provisioning_required(
            fake_port, fake_host, None))
        fake_port['binding:vnic_type'] = 'normal'

        # Test invalid status.
        fake_port['status'] = const.PORT_STATUS_ACTIVE
        self.assertFalse(self.mech_driver._is_port_provisioning_required(
            fake_port, fake_host, None))
        fake_port['status'] = const.PORT_STATUS_DOWN

        # Test no host.
        self.assertFalse(self.mech_driver._is_port_provisioning_required(
            fake_port, None, None))

        # Test invalid host.
        self.sb_ovn.chassis_exists.return_value = False
        self.assertFalse(self.mech_driver._is_port_provisioning_required(
            fake_port, fake_host, None))
        self.sb_ovn.chassis_exists.return_value = True

        # Test port provisioning required.
        self.assertTrue(self.mech_driver._is_port_provisioning_required(
            fake_port, fake_host, None))

    def _test_add_subnet_dhcp_options_in_ovn(self, subnet, ovn_dhcp_opts=None,
                                             call_get_dhcp_opts=True,
                                             call_compose_dhcp_opts=True):
        subnet['id'] = 'fake_id'
        with mock.patch.object(self.mech_driver,
                               'get_ovn_dhcp_options') as get_opts:
            self.mech_driver.add_subnet_dhcp_options_in_ovn(
                subnet, mock.ANY, ovn_dhcp_opts)
            self.assertEqual(call_get_dhcp_opts, get_opts.called)
            self.assertEqual(
                call_compose_dhcp_opts,
                self.mech_driver._nb_ovn.compose_dhcp_options_commands.called)

    def test_add_subnet_dhcp_options_in_ovn(self):
        subnet = {'ip_version': const.IP_VERSION_4}
        self._test_add_subnet_dhcp_options_in_ovn(subnet)

    def test_add_subnet_dhcp_options_in_ovn_with_given_ovn_dhcp_opts(self):
        subnet = {'ip_version': const.IP_VERSION_4}
        self._test_add_subnet_dhcp_options_in_ovn(
            subnet, ovn_dhcp_opts={'foo': 'bar'}, call_get_dhcp_opts=False)

    def test_add_subnet_dhcp_options_in_ovn_with_slaac_v6_subnet(self):
        subnet = {'ip_version': const.IP_VERSION_6,
                  'ipv6_address_mode': const.IPV6_SLAAC}
        self._test_add_subnet_dhcp_options_in_ovn(
            subnet, call_get_dhcp_opts=False, call_compose_dhcp_opts=False)


class OVNMechanismDriverTestCase(test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['logger', 'ovn']

    def setUp(self):
        config.cfg.CONF.set_override('tenant_network_types',
                                     ['geneve'],
                                     group='ml2')
        config.cfg.CONF.set_override('vni_ranges',
                                     ['1:65536'],
                                     group='ml2_type_geneve')
        super(OVNMechanismDriverTestCase, self).setUp()
        mm = manager.NeutronManager.get_plugin().mechanism_manager
        self.mech_driver = mm.mech_drivers['ovn'].obj
        self.mech_driver._nb_ovn = fakes.FakeOvsdbNbOvnIdl()
        self.mech_driver._sb_ovn = fakes.FakeOvsdbSbOvnIdl()
        self.mech_driver._insert_port_provisioning_block = mock.Mock()


class TestOVNMechansimDriverBasicGet(test_plugin.TestMl2BasicGet,
                                     OVNMechanismDriverTestCase):
    pass


class TestOVNMechansimDriverV2HTTPResponse(test_plugin.TestMl2V2HTTPResponse,
                                           OVNMechanismDriverTestCase):
    pass


class TestOVNMechansimDriverNetworksV2(test_plugin.TestMl2NetworksV2,
                                       OVNMechanismDriverTestCase):
    pass


class TestOVNMechansimDriverSubnetsV2(test_plugin.TestMl2SubnetsV2,
                                      OVNMechanismDriverTestCase):

    # NOTE(rtheis): Mock the OVN port update since it is getting subnet
    # information for ACL processing. This interferes with the update_port
    # mock already done by the test.
    def test_subnet_update_ipv4_and_ipv6_pd_v6stateless_subnets(self):
        with mock.patch.object(self.mech_driver, '_update_port_in_ovn'),\
                mock.patch.object(self.mech_driver,
                                  '_get_subnet_dhcp_options_for_port',
                                  return_value={}):
            super(TestOVNMechansimDriverSubnetsV2, self).\
                test_subnet_update_ipv4_and_ipv6_pd_v6stateless_subnets()

    # NOTE(rtheis): Mock the OVN port update since it is getting subnet
    # information for ACL processing. This interferes with the update_port
    # mock already done by the test.
    def test_subnet_update_ipv4_and_ipv6_pd_slaac_subnets(self):
        with mock.patch.object(self.mech_driver, '_update_port_in_ovn'),\
                mock.patch.object(self.mech_driver,
                                  '_get_subnet_dhcp_options_for_port',
                                  return_value={}):
            super(TestOVNMechansimDriverSubnetsV2, self).\
                test_subnet_update_ipv4_and_ipv6_pd_slaac_subnets()


class TestOVNMechansimDriverPortsV2(test_plugin.TestMl2PortsV2,
                                    OVNMechanismDriverTestCase):

    # NOTE(rtheis): Override this test to verify that updating
    # a port MAC fails when the port is bound.
    def test_update_port_mac(self):
        self.check_update_port_mac(
            host_arg={portbindings.HOST_ID: 'fake-host'},
            arg_list=(portbindings.HOST_ID,),
            expected_status=exc.HTTPConflict.code,
            expected_error='PortBound')


class TestOVNMechansimDriverAllowedAddressPairs(
        test_plugin.TestMl2AllowedAddressPairs,
        OVNMechanismDriverTestCase):
    pass


class TestOVNMechansimDriverPortSecurity(
        test_ext_portsecurity.PSExtDriverTestCase,
        OVNMechanismDriverTestCase):
    pass


class TestOVNMechansimDriverSegment(test_segment.HostSegmentMappingTestCase):
    _mechanism_drivers = ['logger', 'ovn']

    def setUp(self):
        super(TestOVNMechansimDriverSegment, self).setUp()
        mm = manager.NeutronManager.get_plugin().mechanism_manager
        self.mech_driver = mm.mech_drivers['ovn'].obj
        self.mech_driver._nb_ovn = fakes.FakeOvsdbNbOvnIdl()
        self.mech_driver._sb_ovn = fakes.FakeOvsdbSbOvnIdl()

    def _test_segment_host_mapping(self):
        # Disable the callback to update SegmentHostMapping by default, so
        # that update_segment_host_mapping is the only path to add the mapping
        registry.unsubscribe(
            self.mech_driver._add_segment_host_mapping_for_segment,
            resources.SEGMENT, events.PRECOMMIT_CREATE)
        host = 'hostname'
        with self.network() as network:
            network = network['network']
        segment1 = self._test_create_segment(
            network_id=network['id'], physical_network='phys_net1',
            segmentation_id=200, network_type='vlan')['segment']

        self._test_create_segment(
            network_id=network['id'],
            segmentation_id=200,
            network_type='geneve')['segment']
        self.mech_driver.update_segment_host_mapping(host, ['phys_net1'])
        segments_host_db = self._get_segments_for_host(host)
        self.assertEqual({segment1['id']}, set(segments_host_db))
        return network['id'], host

    def test_update_segment_host_mapping(self):
        network_id, host = self._test_segment_host_mapping()

        # Update the mapping
        segment2 = self._test_create_segment(
            network_id=network_id, physical_network='phys_net2',
            segmentation_id=201, network_type='vlan')['segment']
        self.mech_driver.update_segment_host_mapping(host, ['phys_net2'])
        segments_host_db = self._get_segments_for_host(host)
        self.assertEqual({segment2['id']}, set(segments_host_db))

    def test_clear_segment_host_mapping(self):
        _, host = self._test_segment_host_mapping()

        # Clear the mapping
        self.mech_driver.update_segment_host_mapping(host, [])
        segments_host_db = self._get_segments_for_host(host)
        self.assertEqual({}, segments_host_db)

    def test_update_segment_host_mapping_with_new_segment(self):
        hostname_with_physnets = {'hostname1': ['phys_net1', 'phys_net2'],
                                  'hostname2': ['phys_net1']}
        ovn_sb_api = self.mech_driver._sb_ovn
        ovn_sb_api.get_chassis_hostname_and_physnets.return_value = (
            hostname_with_physnets)
        self.mech_driver.subscribe()
        with self.network() as network:
            network_id = network['network']['id']
        segment = self._test_create_segment(
            network_id=network_id, physical_network='phys_net2',
            segmentation_id=201, network_type='vlan')['segment']
        segments_host_db1 = self._get_segments_for_host('hostname1')
        # A new SegmentHostMapping should be created for hostname1
        self.assertEqual({segment['id']}, set(segments_host_db1))

        segments_host_db2 = self._get_segments_for_host('hostname2')
        self.assertFalse(set(segments_host_db2))


class TestOVNMechansimDriverDHCPOptions(OVNMechanismDriverTestCase):

    def setUp(self):
        super(TestOVNMechansimDriverDHCPOptions, self).setUp()
        self.orig_get_random_mac = n_utils.get_random_mac
        n_utils.get_random_mac = mock.Mock()
        n_utils.get_random_mac.return_value = '01:02:03:04:05:06'

    def tearDown(self):
        super(TestOVNMechansimDriverDHCPOptions, self).tearDown()
        n_utils.get_random_mac = self.orig_get_random_mac

    def _test_get_ovn_dhcp_options_helper(self, subnet, network,
                                          expected_dhcp_options):
        dhcp_options = self.mech_driver.get_ovn_dhcp_options(subnet, network)
        self.assertEqual(expected_dhcp_options, dhcp_options)

    def test_get_ovn_dhcp_options(self):
        subnet = {'id': 'foo-subnet',
                  'cidr': '10.0.0.0/24',
                  'ip_version': 4,
                  'enable_dhcp': True,
                  'gateway_ip': '10.0.0.1',
                  'dns_nameservers': ['7.7.7.7', '8.8.8.8'],
                  'host_routes': [{'destination': '20.0.0.4',
                                   'nexthop': '10.0.0.100'}]}
        network = {'mtu': 1400}

        expected_dhcp_options = {'cidr': '10.0.0.0/24',
                                 'external_ids': {'subnet_id': 'foo-subnet'}}
        expected_dhcp_options['options'] = {
            'server_id': subnet['gateway_ip'],
            'server_mac': '01:02:03:04:05:06',
            'lease_time': str(12 * 60 * 60),
            'mtu': '1400',
            'router': subnet['gateway_ip'],
            'dns_server': '{7.7.7.7, 8.8.8.8}',
            'classless_static_route':
            '{20.0.0.4,10.0.0.100, 0.0.0.0/0,10.0.0.1}'
        }

        self._test_get_ovn_dhcp_options_helper(subnet, network,
                                               expected_dhcp_options)

    def test_get_ovn_dhcp_options_dhcp_disabled(self):
        subnet = {'id': 'foo-subnet',
                  'cidr': '10.0.0.0/24',
                  'ip_version': 4,
                  'enable_dhcp': False,
                  'gateway_ip': '10.0.0.1',
                  'dns_nameservers': ['7.7.7.7', '8.8.8.8'],
                  'host_routes': [{'destination': '20.0.0.4',
                                   'nexthop': '10.0.0.100'}]}
        network = {'mtu': 1400}

        expected_dhcp_options = {'cidr': '10.0.0.0/24',
                                 'external_ids': {'subnet_id': 'foo-subnet'},
                                 'options': {}}

        self._test_get_ovn_dhcp_options_helper(subnet, network,
                                               expected_dhcp_options)

    def test_get_ovn_dhcp_options_no_gw_ip(self):
        subnet = {'id': 'foo-subnet',
                  'cidr': '10.0.0.0/24',
                  'ip_version': 4,
                  'enable_dhcp': True,
                  'gateway_ip': None,
                  'dns_nameservers': ['7.7.7.7', '8.8.8.8'],
                  'host_routes': [{'destination': '20.0.0.4',
                                   'nexthop': '10.0.0.100'}]}
        network = {'mtu': 1400}

        expected_dhcp_options = {'cidr': '10.0.0.0/24',
                                 'external_ids': {'subnet_id': 'foo-subnet'},
                                 'options': {}}

        self._test_get_ovn_dhcp_options_helper(subnet, network,
                                               expected_dhcp_options)

    def test_get_ovn_dhcp_options_ipv6_subnet(self):
        subnet = {'id': 'foo-subnet',
                  'cidr': 'ae70::/24',
                  'ip_version': 6,
                  'enable_dhcp': True,
                  'dns_nameservers': ['7.7.7.7', '8.8.8.8']}
        network = {'mtu': 1400}

        expected_dhcp_options = {
            'cidr': 'ae70::/24', 'external_ids': {'subnet_id': 'foo-subnet'},
            'options': {'server_id': '01:02:03:04:05:06',
                        'dns_server': '{7.7.7.7, 8.8.8.8}'}}

        self._test_get_ovn_dhcp_options_helper(subnet, network,
                                               expected_dhcp_options)

    def test_get_ovn_dhcp_options_dhcpv6_stateless_subnet(self):
        subnet = {'id': 'foo-subnet',
                  'cidr': 'ae70::/24',
                  'ip_version': 6,
                  'enable_dhcp': True,
                  'dns_nameservers': ['7.7.7.7', '8.8.8.8'],
                  'ipv6_address_mode': const.DHCPV6_STATELESS}
        network = {'mtu': 1400}

        expected_dhcp_options = {
            'cidr': 'ae70::/24', 'external_ids': {'subnet_id': 'foo-subnet'},
            'options': {'server_id': '01:02:03:04:05:06',
                        'dns_server': '{7.7.7.7, 8.8.8.8}',
                        'dhcpv6_stateless': 'true'}}

        self._test_get_ovn_dhcp_options_helper(subnet, network,
                                               expected_dhcp_options)

    def _test__get_port_dhcp_options_port_dhcp_opts_set(self, ip_version=4):
        if ip_version == 4:
            ip_address = '10.0.0.11'
        else:
            ip_address = 'aef0::4'

        port = {
            'id': 'foo-port',
            'device_owner': 'compute:None',
            'fixed_ips': [{'subnet_id': 'foo-subnet',
                           'ip_address': ip_address}]}
        if ip_version == 4:
            port['extra_dhcp_opts'] = [
                {'ip_version': 4, 'opt_name': 'mtu', 'opt_value': '1200'},
                {'ip_version': 4, 'opt_name': 'ntp-server',
                 'opt_value': '8.8.8.8'}]
        else:
            port['extra_dhcp_opts'] = [
                {'ip_version': 6, 'opt_name': 'domain-search',
                 'opt_value': 'foo-domain'},
                {'ip_version': 4, 'opt_name': 'dns-server',
                 'opt_value': '7.7.7.7'}]

        self.mech_driver._get_subnet_dhcp_options_for_port = mock.Mock(
            return_value=({
                'cidr': '10.0.0.0/24',
                'external_ids': {'subnet_id': 'foo-subnet'},
                'options': {'router': '10.0.0.1', 'mtu': '1400'},
                'uuid': 'foo-uuid'} if ip_version == 4 else {
                'cidr': 'aef0::/64',
                'external_ids': {'subnet_id': 'foo-subnet'},
                'options': {'server_id': '01:02:03:04:05:06'}}))

        self.mech_driver._nb_ovn.get_port_dhcp_options.return_value = 'foo-val'
        dhcp_options = self.mech_driver.get_port_dhcp_options(
            port, ip_version)
        self.assertEqual('foo-val', dhcp_options)

        # Since the port has extra DHCP options defined, a new DHCP_Options
        # row should be created and logical switch port DHCPv4/DHCPv6 options
        # should point to this.
        if ip_version == 4:
            expected_dhcp_options = {
                'cidr': '10.0.0.0/24',
                'external_ids': {'subnet_id': 'foo-subnet',
                                 'port_id': 'foo-port'},
                'options': {'router': '10.0.0.1', 'mtu': '1200',
                            'ntp_server': '8.8.8.8'}}
        else:
            expected_dhcp_options = {
                'cidr': 'aef0::/64',
                'external_ids': {'subnet_id': 'foo-subnet',
                                 'port_id': 'foo-port'},
                'options': {'server_id': '01:02:03:04:05:06',
                            'domain_search': 'foo-domain'}}

        self.mech_driver._nb_ovn.add_dhcp_options.assert_called_once_with(
            'foo-subnet', port_id='foo-port', **expected_dhcp_options)

    def test__get_port_dhcp_options_port_dhcp_opts_set_v4(self):
        self._test__get_port_dhcp_options_port_dhcp_opts_set(ip_version=4)

    def test__get_port_dhcp_options_port_dhcp_opts_set_v6(self):
        self._test__get_port_dhcp_options_port_dhcp_opts_set(ip_version=6)

    def _test__get_port_dhcp_options_port_dhcp_opts_not_set(
        self, ip_version=4):
        if ip_version == 4:
            port = {'id': 'foo-port',
                    'device_owner': 'compute:None',
                    'fixed_ips': [{'subnet_id': 'foo-subnet',
                                   'ip_address': '10.0.0.11'}]}
        else:
            port = {'id': 'foo-port',
                    'device_owner': 'compute:None',
                    'fixed_ips': [{'subnet_id': 'foo-subnet',
                                   'ip_address': 'aef0::4'}]}

        if ip_version == 4:
            expected_dhcp_opts = {
                'cidr': '10.0.0.0/24',
                'external_ids': {'subnet_id': 'foo-subnet'},
                'options': {'router': '10.0.0.1', 'mtu': '1400'}}
        else:
            expected_dhcp_opts = {
                'cidr': 'aef0::/64',
                'external_ids': {'subnet_id': 'foo-subnet'},
                'options': {'server_id': '01:02:03:04:05:06'}}

        self.mech_driver._get_subnet_dhcp_options_for_port = mock.Mock(
            return_value=expected_dhcp_opts)

        self.assertEqual(
            expected_dhcp_opts,
            self.mech_driver.get_port_dhcp_options(port,
                                                   ip_version=ip_version))

        # Since the port has no extra DHCPv4/v6 options defined, no new
        # DHCP_Options row should be created and logical switch port DHCPv4/v6
        # options should point to the subnet DHCPv4/v6 options.
        self.mech_driver._nb_ovn.add_dhcp_options.assert_not_called()
        self.mech_driver._nb_ovn.get_port_dhcp_options.assert_not_called()

    def test__get_port_dhcp_options_port_dhcp_opts_not_set_v4(self):
        self._test__get_port_dhcp_options_port_dhcp_opts_not_set(ip_version=4)

    def test__get_port_dhcp_options_port_dhcp_opts_not_set_v6(self):
        self._test__get_port_dhcp_options_port_dhcp_opts_not_set(ip_version=6)

    def _test__get_port_dhcp_options_port_dhcp_disabled(self, ip_version=4):
        port = {
            'id': 'foo-port',
            'device_owner': 'compute:None',
            'fixed_ips': [{'subnet_id': 'foo-subnet',
                           'ip_address': '10.0.0.11'},
                          {'subnet_id': 'foo-subnet-v6',
                           'ip_address': 'aef0::11'}],
            'extra_dhcp_opts': [{'ip_version': 4, 'opt_name': 'dhcp_disabled',
                                 'opt_value': 'False'},
                                {'ip_version': 6, 'opt_name': 'dhcp_disabled',
                                 'opt_value': 'False'}]
            }

        subnet_dhcp_opts = mock.Mock()
        self.mech_driver._get_subnet_dhcp_options_for_port = mock.Mock(
            return_value=subnet_dhcp_opts)

        # No dhcp_disabled set to true, subnet dhcp options will be get for
        # this port. Since it doesn't have any other extra dhcp options, but
        # dhcp_disabled, no port dhcp options will be created.
        self.assertEqual(
            subnet_dhcp_opts,
            self.mech_driver.get_port_dhcp_options(port, ip_version))
        self.assertEqual(
            1,
            self.mech_driver._get_subnet_dhcp_options_for_port.call_count)
        self.mech_driver._nb_ovn.add_dhcp_options.assert_not_called()
        self.mech_driver._nb_ovn.get_port_dhcp_options.assert_not_called()

        # Set dhcp_disabled with ip_version specified by this test case to
        # true, no dhcp options will be get since it's dhcp_disabled now for
        # ip_version be tested.
        opt_index = 0 if ip_version == 4 else 1
        port['extra_dhcp_opts'][opt_index]['opt_value'] = 'True'
        self.mech_driver._get_subnet_dhcp_options_for_port.reset_mock()
        self.assertIsNone(
            self.mech_driver.get_port_dhcp_options(port, ip_version))
        self.assertEqual(
            0,
            self.mech_driver._get_subnet_dhcp_options_for_port.call_count)
        self.mech_driver._nb_ovn.add_dhcp_options.assert_not_called()
        self.mech_driver._nb_ovn.get_port_dhcp_options.assert_not_called()

        # Set dhcp_disabled with ip_version specified by this test case to
        # false, and set dhcp_disabled with ip_version not in test to true.
        # Subnet dhcp options will be get, since dhcp_disabled with ip_version
        # not in test should not affect.
        opt_index_1 = 1 if ip_version == 4 else 0
        port['extra_dhcp_opts'][opt_index]['opt_value'] = 'False'
        port['extra_dhcp_opts'][opt_index_1]['opt_value'] = 'True'
        self.assertEqual(
            subnet_dhcp_opts,
            self.mech_driver.get_port_dhcp_options(port, ip_version))
        self.assertEqual(
            1,
            self.mech_driver._get_subnet_dhcp_options_for_port.call_count)
        self.mech_driver._nb_ovn.add_dhcp_options.assert_not_called()
        self.mech_driver._nb_ovn.get_port_dhcp_options.assert_not_called()

    def test__get_port_dhcp_options_port_dhcp_disabled_v4(self):
        self._test__get_port_dhcp_options_port_dhcp_disabled(ip_version=4)

    def test__get_port_dhcp_options_port_dhcp_disabled_v6(self):
        self._test__get_port_dhcp_options_port_dhcp_disabled(ip_version=6)

    def test__get_port_dhcp_options_port_with_invalid_device_owner(self):
        port = {
            'id': 'foo-port',
            'device_owner': 'neutron:router_interface',
            'fixed_ips': ['fake']
        }

        self.assertIsNone(
            self.mech_driver.get_port_dhcp_options(port, mock.ANY))

    def _test__get_subnet_dhcp_options_for_port(self, ip_version=4,
                                                enable_dhcp=True):
        port = {'fixed_ips': [
            {'ip_address': '10.0.0.4',
             'subnet_id': 'v4_snet_id_1' if enable_dhcp else 'v4_snet_id_2'},
            {'ip_address': '2001:dba::4',
             'subnet_id': 'v6_snet_id_1' if enable_dhcp else 'v6_snet_id_2'},
            {'ip_address': '2001:dbb::4', 'subnet_id': 'v6_snet_id_3'}]}

        def fake(subnets):
            fake_rows = {
                'v4_snet_id_1': 'foo',
                'v6_snet_id_1': {'options': {}},
                'v6_snet_id_3': {'options': {
                    ovn_const.DHCPV6_STATELESS_OPT: 'true'}}}
            return [fake_rows[row] for row in fake_rows if row in subnets]

        self.mech_driver._nb_ovn.get_subnets_dhcp_options.side_effect = fake

        if ip_version == 4:
            expected_opts = 'foo' if enable_dhcp else None
        else:
            expected_opts = {
                'options': {} if enable_dhcp else {
                    ovn_const.DHCPV6_STATELESS_OPT: 'true'}}

        self.assertEqual(
            expected_opts,
            self.mech_driver._get_subnet_dhcp_options_for_port(
                port, ip_version))

    def test__get_subnet_dhcp_options_for_port_v4(self):
        self._test__get_subnet_dhcp_options_for_port()

    def test__get_subnet_dhcp_options_for_port_v4_dhcp_disabled(self):
        self._test__get_subnet_dhcp_options_for_port(enable_dhcp=False)

    def test__get_subnet_dhcp_options_for_port_v6(self):
        self._test__get_subnet_dhcp_options_for_port(ip_version=6)

    def test__get_subnet_dhcp_options_for_port_v6_dhcp_disabled(self):
        self._test__get_subnet_dhcp_options_for_port(ip_version=6,
                                                     enable_dhcp=False)
