#
# Copyright 2019 aiohomekit team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import socket
import sys
from unittest.mock import MagicMock, PropertyMock, call, patch

if sys.version_info[:2] < (3, 8):
    from asynctest.mock import CoroutineMock  # noqa

    AsyncMock = CoroutineMock  # noqa: F405
else:
    from unittest.mock import AsyncMock  # noqa

import pytest
from zeroconf import BadTypeInNameException, Error
from zeroconf.asyncio import AsyncServiceInfo

from aiohomekit.exceptions import AccessoryNotFoundError
from aiohomekit.model.feature_flags import FeatureFlags
from aiohomekit.zeroconf import (
    _service_info_is_homekit_device,
    async_discover_homekit_devices,
    async_find_data_for_device_id,
    async_find_device_ip_and_port,
    get_from_properties,
)


@pytest.fixture
def mock_asynczeroconf():
    """Mock zeroconf."""

    def browser(zeroconf, service, handler):
        # Make sure we get the right mocked object
        if hasattr("zeroconf", "_extract_mock_name"):  # required python 3.7+
            assert zeroconf._extract_mock_name() == "zeroconf_mock"
        handler.add_service(zeroconf, service, f"name.{service}")
        async_browser = MagicMock()
        async_browser.async_cancel = AsyncMock()
        return async_browser

    with patch("aiohomekit.zeroconf.AsyncServiceBrowser") as mock_browser:
        mock_browser.side_effect = browser

        with patch("aiohomekit.zeroconf.AsyncZeroconf") as mock_zc:
            zc = mock_zc.return_value
            zc.async_register_service = AsyncMock()
            zc.async_close = AsyncMock()
            zeroconf = MagicMock(name="zeroconf_mock")
            zeroconf.async_wait_for_start = AsyncMock()
            zc.zeroconf = zeroconf
            yield zc


async def test_find_no_device(mock_asynczeroconf):
    with pytest.raises(AccessoryNotFoundError):
        await async_find_device_ip_and_port("00:00:00:00:00:00", 1)


async def test_find_with_device(mock_asynczeroconf):
    desc = {b"id": b"00:00:02:00:00:02", b"c#": b"1", b"md": b"any"}
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo1._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_find_device_ip_and_port("00:00:02:00:00:02", 1)
    assert result == ("127.0.0.1", 1234)


@pytest.mark.parametrize("exception", [OSError, Error, BadTypeInNameException])
async def test_find_with_device_async_get_service_info_throws(
    exception, mock_asynczeroconf
):
    with patch(
        "aiohomekit.zeroconf.AsyncServiceInfo", side_effect=exception
    ), pytest.raises(AccessoryNotFoundError):
        await async_find_device_ip_and_port("00:00:02:00:00:02", 1)


async def test_async_discover_homekit_devices(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_discover_homekit_devices(max_seconds=1)

    assert result == [
        {
            "address": "127.0.0.1",
            "c#": "1",
            "category": "Lightbulb",
            "ci": "5",
            "ff": 0,
            "flags": FeatureFlags(0),
            "id": "00:00:01:00:00:02",
            "md": "unittest",
            "name": "foo2._hap._tcp.local.",
            "port": 1234,
            "pv": "1.0",
            "s#": "1",
            "sf": "0",
            "statusflags": "Accessory has been paired.",
        }
    ]


async def test_async_discover_homekit_devices_with_service_browser_running(
    mock_asynczeroconf,
):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )

    info2 = AsyncServiceInfo(
        "_hap._tcp.local.",
        "Foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )

    mock_asynczeroconf.zeroconf.cache = MagicMock(
        get_all_by_details=MagicMock(
            return_value=[
                MagicMock(alias="foo._hap._tcp.local."),
                MagicMock(alias="Foo2._hap._tcp.local."),
            ]
        )
    )
    with patch(
        "aiohomekit.zeroconf.AsyncServiceInfo", side_effect=[info, info2]
    ) as asyncserviceinfo_mock, patch(
        "aiohomekit.zeroconf.async_zeroconf_has_hap_service_browser", return_value=True
    ):
        result = await async_discover_homekit_devices(
            max_seconds=1, async_zeroconf_instance=mock_asynczeroconf
        )

    assert result == [
        {
            "address": "127.0.0.1",
            "c#": "1",
            "category": "Lightbulb",
            "ci": "5",
            "ff": 0,
            "flags": FeatureFlags(0),
            "id": "00:00:01:00:00:02",
            "md": "unittest",
            "name": "foo._hap._tcp.local.",
            "port": 1234,
            "pv": "1.0",
            "s#": "1",
            "sf": "0",
            "statusflags": "Accessory has been paired.",
        },
        {
            "address": "127.0.0.1",
            "c#": "1",
            "category": "Lightbulb",
            "ci": "5",
            "ff": 0,
            "flags": FeatureFlags(0),
            "id": "00:00:01:00:00:02",
            "md": "unittest",
            "name": "Foo2._hap._tcp.local.",
            "port": 1234,
            "pv": "1.0",
            "s#": "1",
            "sf": "0",
            "statusflags": "Accessory has been paired.",
        },
    ]

    assert asyncserviceinfo_mock.mock_calls == [
        call("_hap._tcp.local.", "foo._hap._tcp.local."),
        call("_hap._tcp.local.", "Foo2._hap._tcp.local."),
    ]


async def test_async_discover_homekit_devices_with_service_browser_running_not_hap_device(
    mock_asynczeroconf,
):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_nothap._tcp.local.",
        "foo2._nothap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )

    mock_asynczeroconf.zeroconf.cache = MagicMock(
        get_all_by_details=MagicMock(return_value=[])
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info), patch(
        "aiohomekit.zeroconf.async_zeroconf_has_hap_service_browser", return_value=True
    ):
        result = await async_discover_homekit_devices(
            max_seconds=1, async_zeroconf_instance=mock_asynczeroconf
        )

    assert result == []


async def test_async_discover_homekit_devices_with_service_browser_running_invalid_device(
    mock_asynczeroconf,
):
    desc = {
        b"c#": b"1",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )

    mock_asynczeroconf.zeroconf.cache = MagicMock(
        get_all_by_details=MagicMock(
            return_value=[
                MagicMock(alias="foo2._hap._tcp.local."),
            ]
        )
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info), patch(
        "aiohomekit.zeroconf.async_zeroconf_has_hap_service_browser", return_value=True
    ):
        result = await async_discover_homekit_devices(
            max_seconds=1, async_zeroconf_instance=mock_asynczeroconf
        )

    assert result == []


async def test_discover_homekit_devices_missing_c(mock_asynczeroconf):
    desc = {
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_discover_homekit_devices(max_seconds=1)

    assert result == []


async def test_async_discover_homekit_devices_missing_md(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_discover_homekit_devices(max_seconds=1)

    assert result == []


async def test_discover_homekit_devices_shared_zeroconf(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_discover_homekit_devices(
            max_seconds=1, async_zeroconf_instance=mock_asynczeroconf
        )

    assert result == [
        {
            "address": "127.0.0.1",
            "c#": "1",
            "category": "Lightbulb",
            "ci": "5",
            "ff": 0,
            "flags": FeatureFlags(0),
            "id": "00:00:01:00:00:02",
            "md": "unittest",
            "name": "foo2._hap._tcp.local.",
            "port": 1234,
            "pv": "1.0",
            "s#": "1",
            "sf": "0",
            "statusflags": "Accessory has been paired.",
        }
    ]


async def test_async_find_data_for_device_id_matches(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        result = await async_find_data_for_device_id(
            device_id="00:00:01:00:00:02",
            max_seconds=1,
            async_zeroconf_instance=mock_asynczeroconf,
        )

    assert result == {
        "address": "127.0.0.1",
        "c#": "1",
        "category": "Lightbulb",
        "ci": "5",
        "ff": 0,
        "flags": FeatureFlags(0),
        "id": "00:00:01:00:00:02",
        "md": "unittest",
        "name": "foo2._hap._tcp.local.",
        "port": 1234,
        "pv": "1.0",
        "s#": "1",
        "sf": "0",
        "statusflags": "Accessory has been paired.",
    }


async def test_async_find_data_for_device_id_does_not_match(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:03",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        with pytest.raises(AccessoryNotFoundError):
            await async_find_data_for_device_id(
                device_id="00:00:01:00:00:02",
                max_seconds=1,
                async_zeroconf_instance=mock_asynczeroconf,
            )


async def test_async_find_data_for_device_id_info_without_id(mock_asynczeroconf):
    desc = {
        b"c#": b"1",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )
    with patch("aiohomekit.zeroconf.AsyncServiceInfo", return_value=info):
        with pytest.raises(AccessoryNotFoundError):
            await async_find_data_for_device_id(
                device_id="00:00:01:00:00:02",
                max_seconds=1,
                async_zeroconf_instance=mock_asynczeroconf,
            )


async def test_async_find_data_for_device_id_with_active_service_browser(
    mock_asynczeroconf,
):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"ff": b"3",
        b"sf": b"0",
    }
    mock_asynczeroconf.zeroconf.cache = MagicMock(
        get_all_by_details=MagicMock(
            return_value=[
                MagicMock(alias="foo2._hap._tcp.local."),
            ]
        )
    )
    with patch(
        "aiohomekit.zeroconf.async_zeroconf_has_hap_service_browser", return_value=True
    ), patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.load_from_cache", return_value=True
    ) as mock_load_from_cache, patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.properties",
        PropertyMock(return_value=desc),
    ), patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.addresses",
        PropertyMock(return_value=[socket.inet_aton("127.0.0.1")]),
    ):
        result = await async_find_data_for_device_id(
            device_id="00:00:01:00:00:02",
            max_seconds=1,
            async_zeroconf_instance=mock_asynczeroconf,
        )

    assert mock_load_from_cache.called

    assert result == {
        "address": "127.0.0.1",
        "c#": "1",
        "category": "Lightbulb",
        "ci": "5",
        "ff": 3,
        "flags": FeatureFlags(3),
        "id": "00:00:01:00:00:02",
        "md": "unittest",
        "name": "foo2._hap._tcp.local.",
        "port": None,
        "pv": "1.0",
        "s#": "1",
        "sf": "0",
        "statusflags": "Accessory has been paired.",
    }


async def test_async_find_data_for_device_id_with_active_service_browser_no_match(
    mock_asynczeroconf,
):
    desc = {
        b"c#": b"1",
        b"id": b"00:00:01:00:00:03",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    mock_asynczeroconf.zeroconf.cache = MagicMock(
        get_all_by_details=MagicMock(
            return_value=[
                MagicMock(alias="foo2._hap._tcp.local."),
            ]
        )
    )
    with patch(
        "aiohomekit.zeroconf.async_zeroconf_has_hap_service_browser", return_value=True
    ), patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.load_from_cache", return_value=True
    ) as mock_load_from_cache, patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.properties",
        PropertyMock(return_value=desc),
    ), patch(
        "aiohomekit.zeroconf.AsyncServiceInfo.addresses",
        PropertyMock(return_value=[socket.inet_aton("127.0.0.1")]),
    ), pytest.raises(
        AccessoryNotFoundError
    ):
        await async_find_data_for_device_id(
            device_id="00:00:01:00:00:02",
            max_seconds=1,
            async_zeroconf_instance=mock_asynczeroconf,
        )

    assert mock_load_from_cache.called


def test_existing_key():
    props = {"c#": "259"}
    val = get_from_properties(props, "c#")
    assert "259" == val


def test_non_existing_key_no_default():
    props = {"c#": "259"}
    val = get_from_properties(props, "s#")
    assert val is None


def test_non_existing_key_case_insensitive():
    props = {"C#": "259", "heLLo": "World"}
    val = get_from_properties(props, "c#")
    assert None is val
    val = get_from_properties(props, "c#", case_sensitive=True)
    assert None is val
    val = get_from_properties(props, "c#", case_sensitive=False)
    assert "259" == val

    val = get_from_properties(props, "HEllo", case_sensitive=False)
    assert "World" == val


def test_non_existing_key_with_default():
    props = {"c#": "259"}
    val = get_from_properties(props, "s#", default="1")
    assert "1" == val


def test_non_existing_key_with_default_non_string():
    props = {"c#": "259"}
    val = get_from_properties(props, "s#", default=1)
    assert "1" == val


def test_is_homekit_device_case_insensitive():
    desc = {
        b"C#": b"1",
        b"id": b"00:00:01:00:00:02",
        b"md": b"unittest",
        b"s#": b"1",
        b"ci": b"5",
        b"sf": b"0",
    }
    info = AsyncServiceInfo(
        "_hap._tcp.local.",
        "foo2._hap._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=1234,
        properties=desc,
        weight=0,
        priority=0,
    )

    assert _service_info_is_homekit_device(info)
