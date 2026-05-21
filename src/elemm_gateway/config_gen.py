import platform
import os
import sys
import json
import getpass
import shutil

class Colors:
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ENDC = '\033[0m'

def run_config_generator():
    print(f"\n{Colors.CYAN}{Colors.BOLD}╔════════════════════════════════════════════════════╗")
    print(f"║       🚀 ELEMM GATEWAY MCP CONFIG GENERATOR        ║")
    print(f"╚════════════════════════════════════════════════════╝{Colors.ENDC}")
    print(f"{Colors.DIM}Auto-detects your system and generates a ready-to-use JSON config.{Colors.ENDC}\n")

    print(f"{Colors.BOLD}1. Transport Method{Colors.ENDC}")
    print(f"  {Colors.CYAN}[1]{Colors.ENDC} STDIO (Local App) {Colors.DIM}- Default{Colors.ENDC}")
    print(f"  {Colors.CYAN}[2]{Colors.ENDC} SSE (Remote via HTTP)")
    t_input = input(f"{Colors.YELLOW}Select [1/2]: {Colors.ENDC}").strip()
    transport = "sse" if t_input == "2" else "stdio"

    host_ip = "localhost"
    port = 8000
    if transport == "sse":
        print(f"\n{Colors.BOLD}2. SSE Bridge URL{Colors.ENDC}")
        print(f"  {Colors.DIM}Press Enter for default: http://localhost:8000/sse{Colors.ENDC}")
        url_input = input(f"{Colors.YELLOW}URL: {Colors.ENDC}").strip()
        url = url_input if url_input else "http://localhost:8000/sse"
    else:
        url = ""

    print(f"\n{Colors.BOLD}3. Client-Session-ID {Colors.DIM}(Optional){Colors.ENDC}")
    print(f"  {Colors.DIM}This will be passed as --name to identify the client{Colors.ENDC}")
    client_session_id = input(f"{Colors.YELLOW}Session-ID: {Colors.ENDC}").strip()

    print(f"\n{Colors.BOLD}4. Deployment Type{Colors.ENDC}")
    print(f"  {Colors.CYAN}[1]{Colors.ENDC} Auto-Detect Native {Colors.DIM}- Default{Colors.ENDC}")
    print(f"  {Colors.CYAN}[2]{Colors.ENDC} Docker Container")
    deploy_input = input(f"{Colors.YELLOW}Select [1/2]: {Colors.ENDC}").strip()
    deployment = "docker" if deploy_input == "2" else "auto"

    print(f"\n{Colors.CYAN}⚙️  Analyzing System Environment...{Colors.ENDC}")
    
    os_type = "linux"
    wsl_distro = ""
    if platform.system().lower() == "windows":
        os_type = "windows"
    elif "microsoft" in platform.release().lower() or "wsl" in platform.release().lower():
        os_type = "wsl"
        wsl_distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    elif platform.system().lower() == "darwin":
        os_type = "mac"

    user = getpass.getuser()
    executable_path = shutil.which("elemm-gateway")
    if not executable_path:
        executable_path = f"{sys.executable} -m elemm_gateway.cli"

    print(f"   {Colors.DIM}• OS: {os_type.upper()}" + (f" ({wsl_distro})" if wsl_distro else "") + f"{Colors.ENDC}")
    print(f"   {Colors.DIM}• User: {user}{Colors.ENDC}")
    print(f"   {Colors.DIM}• Binary: {executable_path}{Colors.ENDC}\n")

    base_args = []
    if client_session_id:
        base_args.extend(["--name", client_session_id])
        
    if transport == "stdio":
        base_args.extend(["--transport", "stdio"])
    else:
        base_args.extend(["--bridge", url])

    if deployment == "docker":
        final_command = "docker"
        final_args = [
            "run", "-i", "--rm", "--network", "host",
            "ghcr.io/v3rm1ll1on/elemm:latest", "elemm-gateway"
        ] + base_args
    else:
        if os_type == "wsl":
            final_command = "wsl.exe"
            cmd_string = f"{executable_path} {' '.join(base_args)}"
            final_args = [
                "-d", wsl_distro if wsl_distro else "Ubuntu",
                "-u", user, "bash", "-c", cmd_string
            ]
        else:
            if " -m " in executable_path:
                parts = executable_path.split(" -m ")
                final_command = parts[0]
                final_args = ["-m", parts[1]] + base_args
            else:
                final_command = executable_path
                final_args = base_args

    config = {
        "mcpServers": {
            "elemm-gateway": {
                "command": final_command,
                "args": final_args
            }
        }
    }

    json_str = json.dumps(config, indent=2)
    
    print(f"{Colors.GREEN}{Colors.BOLD}✅ Configuration Generated Successfully!{Colors.ENDC}")
    print(f"{Colors.DIM}Copy and paste this into your MCP Client Config (e.g. claude_desktop_config.json):{Colors.ENDC}\n")
    
    # Print JSON with slight cyan tint for code block feel
    print(f"{Colors.CYAN}{json_str}{Colors.ENDC}\n")
    print(f"{Colors.BOLD}──────────────────────────────────────────────────────{Colors.ENDC}\n")

if __name__ == "__main__":
    run_config_generator()
