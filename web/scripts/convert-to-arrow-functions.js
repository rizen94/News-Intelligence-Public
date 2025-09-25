#!/usr/bin/env node
/**
 * Script to convert function declarations to arrow functions
 * Run with: node scripts/convert-to-arrow-functions.js
 */

const fs = require('fs');
const path = require('path');

// Directory to process
const srcDir = path.join(__dirname, '..', 'src');

// Files to process
const fileExtensions = ['.js', '.jsx', '.ts', '.tsx'];

// Function to get all files recursively
function getAllFiles(dir, extensions) {
  let files = [];
  const items = fs.readdirSync(dir);
  
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);
    
    if (stat.isDirectory()) {
      files = files.concat(getAllFiles(fullPath, extensions));
    } else if (extensions.some(ext => item.endsWith(ext))) {
      files.push(fullPath);
    }
  }
  
  return files;
}

// Function to convert function declarations to arrow functions
function convertToArrowFunctions(content) {
  let modified = false;
  
  // Pattern 1: export default function ComponentName() { ... }
  const exportDefaultFunctionPattern = /export\s+default\s+function\s+(\w+)\s*\(([^)]*)\)\s*{/g;
  content = content.replace(exportDefaultFunctionPattern, (match, funcName, params) => {
    modified = true;
    return `const ${funcName} = (${params}) => {`;
  });
  
  // Pattern 2: function ComponentName() { ... }
  const functionDeclarationPattern = /^function\s+(\w+)\s*\(([^)]*)\)\s*{/gm;
  content = content.replace(functionDeclarationPattern, (match, funcName, params) => {
    // Skip if it's already an arrow function or if it's a class method
    if (content.includes(`const ${funcName} =`) || content.includes(`class ${funcName}`)) {
      return match;
    }
    modified = true;
    return `const ${funcName} = (${params}) => {`;
  });
  
  // Pattern 3: export function functionName() { ... }
  const exportFunctionPattern = /export\s+function\s+(\w+)\s*\(([^)]*)\)\s*{/g;
  content = content.replace(exportFunctionPattern, (match, funcName, params) => {
    modified = true;
    return `export const ${funcName} = (${params}) => {`;
  });
  
  // Pattern 4: function functionName() { ... } (not at start of line)
  const inlineFunctionPattern = /(\s+)function\s+(\w+)\s*\(([^)]*)\)\s*{/g;
  content = content.replace(inlineFunctionPattern, (match, spaces, funcName, params) => {
    modified = true;
    return `${spaces}const ${funcName} = (${params}) => {`;
  });
  
  return { content, modified };
}

// Function to process a single file
function processFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const { content: newContent, modified } = convertToArrowFunctions(content);
    
    if (modified) {
      fs.writeFileSync(filePath, newContent, 'utf8');
      return true;
    }
    
    return false;
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return false;
  }
}

// Main execution
console.log('🔄 Converting function declarations to arrow functions...\n');

const files = getAllFiles(srcDir, fileExtensions);
let processedFiles = 0;
let modifiedFiles = 0;

console.log(`Found ${files.length} files to process:\n`);

for (const file of files) {
  console.log(`Processing: ${path.relative(srcDir, file)}`);
  
  if (processFile(file)) {
    modifiedFiles++;
    console.log(`  ✅ Converted to arrow functions`);
  } else {
    console.log(`  ⏭️  No changes needed`);
  }
  
  processedFiles++;
}

console.log(`\n📊 Summary:`);
console.log(`  Files processed: ${processedFiles}`);
console.log(`  Files modified: ${modifiedFiles}`);
console.log(`  Files unchanged: ${processedFiles - modifiedFiles}`);

if (modifiedFiles > 0) {
  console.log(`\n✅ Function declarations successfully converted to arrow functions!`);
  console.log(`\nNext steps:`);
  console.log(`  1. Run: npm run lint:fix`);
  console.log(`  2. Run: npm run format`);
  console.log(`  3. Test the application to ensure everything works`);
} else {
  console.log(`\nℹ️  No function declarations found to convert.`);
}

console.log(`\n🎉 Arrow function conversion complete!`);
