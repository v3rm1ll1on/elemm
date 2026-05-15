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
    def squish(data: Any, select: Optional[Any] = None, filter_str: Optional[Any] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> tuple[Any, bool, int]:
        """
        Filters and paginates data. Returns (squished_data, was_truncated, total_count).
        """
        if data is None:
            return None, False, 0
            
        was_truncated = False
        total_count = 0

        # 1. Filter by key=val (or dict)
        if filter_str and isinstance(data, list):
            if isinstance(filter_str, str) and "=" in filter_str:
                k, v = filter_str.split("=", 1)
                data = [item for item in data if str(item.get(k)) == v]
            elif isinstance(filter_str, dict):
                for k, v in filter_str.items():
                    data = [item for item in data if str(item.get(k)) == str(v)]
        
        # 2. Virtual Pagination (Lists and Strings)
        if isinstance(data, (list, str)):
            total_count = len(data)
            start = offset if offset is not None else 0
            end = (start + limit) if limit is not None else None
            
            if (end is not None and total_count > end) or start > 0:
                was_truncated = True
                
            data = data[start:end] if end is not None else data[start:]
        
        # 3. Select fields (nested)
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
                elif isinstance(data, dict):
                    data = ResponseSquisher._pick_fields(data, fields)
                
        return data, was_truncated, total_count

    @staticmethod
    def smart_truncate(data: Any, max_list_items: int = 20, max_string_length: int = 10000) -> Any:
        """
        Recursively truncates large data structures to keep them context-friendly 
        while maintaining valid JSON structure.
        """
        if isinstance(data, list):
            if len(data) > max_list_items:
                truncated = [ResponseSquisher.smart_truncate(item, max_list_items, max_string_length) for item in data[:max_list_items]]
                truncated.append({"_elemm_info": f"Truncated: {len(data) - max_list_items} more items hidden. Use '_limit' or '_filter' to see more."})
                return truncated
            return [ResponseSquisher.smart_truncate(item, max_list_items, max_string_length) for item in data]
            
        if isinstance(data, dict):
            return {k: ResponseSquisher.smart_truncate(v, max_list_items, max_string_length) for k, v in data.items()}
            
        if isinstance(data, str):
            if len(data) > max_string_length:
                return data[:max_string_length] + f"... [TRUNCATED: {len(data) - max_string_length} more characters]"
                
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
