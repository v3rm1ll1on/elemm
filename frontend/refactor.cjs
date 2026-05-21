const fs = require('fs');
let file = fs.readFileSync('src/components/MCPSettings.jsx', 'utf8');

if (!file.includes("import { Input, Select, Button, Switch, FormGroup }")) {
  file = file.replace("import { API_BASE } from '../config';", "import { API_BASE } from '../config';\nimport { Input, Select, Button, Switch, FormGroup } from './ui';");
}

file = file.replace(/<button/g, '<Button');
file = file.replace(/<\/button>/g, '</Button>');

file = file.replace(/<select/g, '<Select');
file = file.replace(/<\/select>/g, '</Select>');

file = file.replace(/<input/g, '<Input');
file = file.replace(/<Input([^>]*?type="checkbox"([^>]*?))\/>/g, '<Switch$1/>');
file = file.replace(/<Input([^>]*?type='checkbox'([^>]*?))\/>/g, '<Switch$1/>');

// Also try to replace <div className="mcp-form-group"> ... </div> with <FormGroup> ... </FormGroup> if possible? No, too risky.

fs.writeFileSync('src/components/MCPSettings.jsx', file);
console.log("Refactoring complete.");
