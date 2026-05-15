# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import Any, Dict, List, Optional

class ResponseSquisher:
    """Handles context hygiene by filtering JSON responses."""
    @staticmethod
    def squish(data: Any, select: Optional[Any] = None, filter_str: Optional[Any] = None) -> Any:
        if not data:
            return data
            
        # 1. Filter by key=val (or dict)
        if filter_str and isinstance(data, list):
            if isinstance(filter_str, str) and "=" in filter_str:
                k, v = filter_str.split("=", 1)
                data = [item for item in data if str(item.get(k)) == v]
            elif isinstance(filter_str, dict):
                for k, v in filter_str.items():
                    data = [item for item in data if str(item.get(k)) == str(v)]
        
        # 2. Select fields (nested)
        if select:
            if isinstance(select, str):
                fields = [f.strip() for f in select.split(",")]
            elif isinstance(select, list):
                fields = [str(f).strip() for f in select]
            else:
                fields = []
                
            if fields:
                if isinstance(data, list):
                    data = [ResponseSquisher._pick_fields(item, fields) for item in data]
                else:
                    data = ResponseSquisher._pick_fields(data, fields)
                
        return data

    @staticmethod
    def _pick_fields(obj: Any, fields: List[str]) -> Dict[str, Any]:
        if not isinstance(obj, dict):
            return obj
        res = {}
        for f in fields:
            if "." in f:
                parts = f.split(".", 1)
                if parts[0] in obj:
                    nested_val = ResponseSquisher._pick_fields(obj[parts[0]], [parts[1]])
                    if parts[0] not in res:
                        res[parts[0]] = {}
                    if isinstance(res[parts[0]], dict) and isinstance(nested_val, dict):
                        res[parts[0]].update(nested_val)
                    else:
                        res[parts[0]] = nested_val
            elif f in obj:
                res[f] = obj[f]
        return res
