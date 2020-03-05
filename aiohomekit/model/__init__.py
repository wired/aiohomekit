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

import json
from typing import Any, Dict, Iterable, List, Optional

from .categories import Categories
from .characteristics import (
    CharacteristicFormats,
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from .feature_flags import FeatureFlags
from .mixin import ToDictMixin, get_id
from .services import Service, ServicesTypes

__all__ = [
    "Categories",
    "CharacteristicPermissions",
    "CharacteristicFormats",
    "FeatureFlags",
    "Accessory",
]


class Services:
    def __init__(self):
        self._services: List[Service] = []

    def __iter__(self):
        return iter(self._services)

    def iid(self, iid: int) -> Service:
        return next(filter(lambda service: service.iid == iid, self._services))

    def filter(
        self,
        *,
        service_type: str = None,
        characteristics: Dict[str, str] = None,
        parent_service: Service = None,
        child_service: Service = None,
    ) -> Iterable[Service]:
        matches = iter(self._services)

        if service_type:
            service_type = ServicesTypes.get_uuid(service_type)
            matches = filter(lambda service: service.type == service_type, matches)

        if characteristics:
            for characteristic, value in characteristics.items():
                matches = filter(
                    lambda service: service[characteristic].value == value, matches
                )

        if parent_service:
            matches = filter(lambda service: service in parent_service.linked, matches)

        if child_service:
            matches = filter(lambda service: child_service in service.linked, matches)

        return matches

    def first(
        self,
        *,
        service_type: str = None,
        characteristics: Dict[str, str] = None,
        parent_service: Service = None,
        child_service: Service = None,
    ) -> Service:
        try:
            return next(
                self.filter(
                    service_type=service_type,
                    characteristics=characteristics,
                    parent_service=parent_service,
                    child_service=child_service,
                )
            )
        except StopIteration:
            return None

    def append(self, service: Service):
        self._services.append(service)


class Accessory(ToDictMixin):
    def __init__(self):
        self.aid = get_id()
        self._next_id = 0
        self.services = Services()

    @classmethod
    def create_with_info(
        cls,
        name: str,
        manufacturer: str,
        model: str,
        serial_number: str,
        firmware_revision: str,
    ) -> "Accessory":
        self = cls()

        accessory_info = self.add_service(ServicesTypes.ACCESSORY_INFORMATION)
        accessory_info.add_char(CharacteristicsTypes.IDENTIFY, description="Identify")
        accessory_info.add_char(CharacteristicsTypes.NAME, value=name)
        accessory_info.add_char(CharacteristicsTypes.MANUFACTURER, value=manufacturer)
        accessory_info.add_char(CharacteristicsTypes.MODEL, value=model)
        accessory_info.add_char(CharacteristicsTypes.SERIAL_NUMBER, value=serial_number)
        accessory_info.add_char(
            CharacteristicsTypes.FIRMWARE_REVISION, value=firmware_revision
        )

        return self

    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> "Accessory":
        accessory = cls()
        accessory.aid = data["aid"]

        for service_data in data["services"]:
            service = accessory.add_service(service_data["type"], add_required=False)
            service.iid = service_data["iid"]

            for char_data in service_data["characteristics"]:
                kwargs = {
                    "perms": char_data["perms"],
                    "format": char_data["format"],
                }

                if "description" in char_data:
                    kwargs["description"] = char_data["description"]
                if "value" in char_data:
                    kwargs["value"] = char_data["value"]
                if "minValue" in char_data:
                    kwargs["min_value"] = char_data["minValue"]
                if "maxValue" in char_data:
                    kwargs["max_value"] = char_data["maxValue"]
                if "valid-values" in char_data:
                    kwargs["valid_values"] = char_data["valid-values"]
                if "unit" in char_data:
                    kwargs["unit"] = char_data["unit"]
                if "minStep" in char_data:
                    kwargs["min_step"] = char_data["minStep"]
                if "maxLen" in char_data:
                    kwargs["max_len"] = char_data["maxLen"]

                char = service.add_char(char_data["type"], **kwargs)
                char.iid = char_data["iid"]

        for service_data in data["services"]:
            for linked_service in service_data.get("linked", []):
                accessory.services.iid(service_data["iid"]).add_linked_service(
                    accessory.services.iid(linked_service)
                )

        return accessory

    def get_next_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def add_service(
        self, service_type: str, name: Optional[str] = None, add_required: bool = False
    ) -> Service:
        service = Service(self, service_type, name=name, add_required=add_required)
        self.services.append(service)
        return service

    def to_accessory_and_service_list(self):
        services_list = []
        for s in self.services:
            services_list.append(s.to_accessory_and_service_list())
        d = {"aid": self.aid, "services": services_list}
        return d


class Accessories(ToDictMixin):
    def __init__(self) -> None:
        self.accessories = []

    def __iter__(self):
        return iter(self.accessories)

    def __getitem__(self, idx):
        return self.accessories[idx]

    @classmethod
    def from_file(cls, path):
        with open(path) as fp:
            return cls.from_list(json.load(fp))

    @classmethod
    def from_list(cls, accessories):
        self = cls()
        for accessory in accessories:
            self.add_accessory(Accessory.create_from_dict(accessory))
        return self

    def add_accessory(self, accessory: Accessory) -> None:
        self.accessories.append(accessory)

    def serialize(self):
        accessories_list = []
        for a in self.accessories:
            accessories_list.append(a.to_accessory_and_service_list())
        return accessories_list

    def to_accessory_and_service_list(self):
        d = {"accessories": self.serialize()}
        return json.dumps(d)

    def aid(self, aid) -> Accessory:
        return next(filter(lambda accessory: accessory.aid == aid, self.accessories))
