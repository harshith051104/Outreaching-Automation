const fs = require('fs');
const code = fs.readFileSync('src/app/dashboard/outreach-tracker/page.tsx', 'utf8');

let braces = [];
let parens = [];
let inString = false;
let stringChar = '';
let inComment = false;
let inLineComment = false;

let lines = code.split('\n');
for (let i = 0; i < lines.length; i++) {
  let line = lines[i];
  inLineComment = false;
  for (let j = 0; j < line.length; j++) {
    let char = line[j];
    let nextChar = line[j + 1] || '';
    
    if (inComment) {
      if (char === '*' && nextChar === '/') {
        inComment = false;
        j++;
      }
      continue;
    }
    
    if (inLineComment) {
      continue;
    }
    
    if (inString) {
      if (char === '\\') {
        j++; // skip next char
        continue;
      }
      if (char === stringChar) {
        inString = false;
      }
      continue;
    }
    
    if (char === '/' && nextChar === '/') {
      inLineComment = true;
      j++;
      continue;
    }
    
    if (char === '/' && nextChar === '*') {
      inComment = true;
      j++;
      continue;
    }
    
    if (char === '"' || char === "'" || char === '`') {
      inString = true;
      stringChar = char;
      continue;
    }
    
    if (char === '{') {
      braces.push({ type: '{', line: i + 1, col: j + 1 });
    } else if (char === '}') {
      if (braces.length === 0) {
        console.log(`Unmatched } at line ${i + 1}:${j + 1}`);
      } else {
        braces.pop();
      }
    } else if (char === '(') {
      parens.push({ type: '(', line: i + 1, col: j + 1 });
    } else if (char === ')') {
      if (parens.length === 0) {
        console.log(`Unmatched ) at line ${i + 1}:${j + 1}`);
      } else {
        parens.pop();
      }
    }
  }
}

console.log(`Remaining open braces: ${braces.length}`);
if (braces.length > 0) {
  console.log('Open braces details (last 5):', braces.slice(-5));
}
console.log(`Remaining open parens: ${parens.length}`);
if (parens.length > 0) {
  console.log('Open parens details (last 5):', parens.slice(-5));
}
