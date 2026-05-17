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
    def parse_gql_selection(s: str) -> List[str]:
        """Parses a GraphQL/Elemm selection string, expanding nested brace constructs into dot-notation."""
        s = s.replace("{", " { ").replace("}", " } ").replace(",", " ")
        tokens = s.split()
        results = []
        
        def parse(tokens_iter, prefix=""):
            last_field = None
            for t in tokens_iter:
                if t == "{":
                    if last_field:
                        full_last = f"{prefix}.{last_field}" if prefix else last_field
                        if full_last in results:
                            results.remove(full_last)
                        sub_prefix = full_last
                        parse(tokens_iter, sub_prefix)
                    else:
                        parse(tokens_iter, prefix)
                elif t == "}":
                    return
                else:
                    last_field = t
                    full_field = f"{prefix}.{t}" if prefix else t
                    results.append(full_field)

        parse(iter(tokens))
        return results

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
            fields = []
            if isinstance(select, str):
                fields = ResponseSquisher.parse_gql_selection(select)
            elif isinstance(select, list):
                for item in select:
                    fields.extend(ResponseSquisher.parse_gql_selection(str(item)))
                
            if fields:
                if isinstance(data, list):
                    data = [ResponseSquisher._pick_fields(item, fields) for item in data]
                elif isinstance(data, dict):
                    data = ResponseSquisher._pick_fields(data, fields)
                
        return data, was_truncated, total_count

    @staticmethod
    def smart_truncate(data: Any, max_list_items: int = 20, max_string_length: int = 10000) -> tuple[Any, bool]:
        """
        Recursively truncates large data structures while tracking if truncation happened.
        Returns (truncated_data, was_truncated).
        """
        was_truncated = False

        if isinstance(data, list):
            new_list = []
            if len(data) > max_list_items:
                was_truncated = True
                items_to_process = data[:max_list_items]
            else:
                items_to_process = data

            for item in items_to_process:
                item_data, item_trunc = ResponseSquisher.smart_truncate(item, max_list_items, max_string_length)
                new_list.append(item_data)
                if item_trunc: was_truncated = True
            
            if len(data) > max_list_items:
                new_list.append({"_elemm_info": f"Truncated: {len(data) - max_list_items} more items hidden. Use '_limit' or '_filter' to see more."})
            
            return new_list, was_truncated
            
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                val_data, val_trunc = ResponseSquisher.smart_truncate(v, max_list_items, max_string_length)
                new_dict[k] = val_data
                if val_trunc: was_truncated = True
            return new_dict, was_truncated
            
        if isinstance(data, str):
            if len(data) > max_string_length:
                return data[:max_string_length] + f"... [TRUNCATED: {len(data) - max_string_length} more characters]", True
                
        return data, was_truncated

    @staticmethod
    def _pick_fields(obj: Any, fields: List[str]) -> Any:
        if isinstance(obj, list):
            return [ResponseSquisher._pick_fields(item, fields) for item in obj]
            
        if not isinstance(obj, dict):
            return obj
            
        res = {}
        for f in fields:
            if "." in f:
                parts = f.split(".", 1)
                if parts[0] in obj:
                    nested_val = ResponseSquisher._pick_fields(obj[parts[0]], [parts[1]])
                    if parts[0] not in res:
                        res[parts[0]] = nested_val
                    else:
                        res[parts[0]] = ResponseSquisher._merge_objects(res[parts[0]], nested_val)
            elif f in obj:
                if f in res:
                    res[f] = ResponseSquisher._merge_objects(res[f], obj[f])
                else:
                    res[f] = obj[f]
        return res

    @staticmethod
    def _merge_objects(old: Any, new: Any) -> Any:
        if isinstance(old, dict) and isinstance(new, dict):
            merged = old.copy()
            for k, v in new.items():
                if k in merged:
                    merged[k] = ResponseSquisher._merge_objects(merged[k], v)
                else:
                    merged[k] = v
            return merged
        if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            return [ResponseSquisher._merge_objects(o, n) for o, n in zip(old, new)]
        return new
