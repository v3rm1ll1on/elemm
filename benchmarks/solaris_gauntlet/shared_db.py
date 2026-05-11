"# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
nimport random from typing import Dict, List, Any def get_shared_database() -> Dict[str, Any]: """ Returns the initial static data for the Solaris Benchmark. This ensures both Classic and Elemm versions use the same ground truth. """ db = { "soc": [], "noc": {}, "it": {}, "banking": {}, "finance": {}, "hr": {} } # SOC: Security Alerts for i in range(20): is_incident = (i == 2) db["soc"].append({ "id": "SEC-9982" if is_incident else f"SEC-{1000+i}", "level": "HIGH" if is_incident else "LOW", "msg": "Malicious Exfiltration Detected" if is_incident else f"Anomaly {i}" }) # NOC: IP to Hostname for i in range(50): db["noc"][f"10.0.4.{100+i}"] = f"SRV-NODE-{i}" db["noc"]["10.0.4.142"] = "SRV-FORENSIC-142" # HR: Employee ID to Username for i in range(50): db["hr"][f"EMP-{5000+i}"] = f"USER_{i}" db["hr"]["EMP-8821"] = "CORP-BS-09" # Banking & Finance db["banking"]["RT-EXFIL-99"] = "ACC-FIN-88" db["finance"]["ACC-FIN-88"] = "EMP-8821" # IT: Node Logs for i in range(10): hostname = "SRV-FORENSIC-142" if i == 5 else f"SRV-NODE-{500+i}" logs = [{"ts": "10:00", "user": "SYSTEM", "action": "BOOT"}] if i == 5: logs.append({ "ts": "10:05", "user": "CORP-BS-09", "action": "EXFIL", "token": "RT-EXFIL-99" }) db["it"][hostname] = logs return db"
