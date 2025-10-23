#!/usr/bin/env node
/**
 * Script to replace console statements with Logger utility
 * Run with: node scripts/replace-console-logs.js
 */

const fs = require('fs');
const path = require('path');

// Directory to process
const srcDir = path.join(__dirname, '..', 'src');

// Files to process
const fileExtensions = ['.js', '.jsx'];

// Console methods to replace
const consoleMethods = {
  'console.log': 'Logger.info',
  'console.error': 'Logger.error',
  'console.warn': 'Logger.warn',
  'console.debug': 'Logger.debug'
};

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

// Function to replace console statements in a file
function replaceConsoleInFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let modified = false;
    
    // Check if file already imports Logger
    const hasLoggerImport = content.includes("import Logger from");
    const hasLoggerRequire = content.includes("require('Logger')");
    
    // Replace console statements
    for (const [consoleMethod, loggerMethod] of Object.entries(consoleMethods)) {
      const regex = new RegExp(consoleMethod.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
      if (content.includes(consoleMethod)) {
        content = content.replace(regex, loggerMethod);
        modified = true;
        console.log(`  ✓ Replaced ${consoleMethod} with ${loggerMethod}`);
      }
    }
    
    // Add Logger import if needed and file was modified
    if (modified && !hasLoggerImport && !hasLoggerRequire) {
      // Find the last import statement
      const importRegex = /^import\s+.*?from\s+['"][^'"]+['"];?\s*$/gm;
      const imports = content.match(importRegex);
      
      if (imports && imports.length > 0) {
        const lastImport = imports[imports.length - 1];
        const lastImportIndex = content.lastIndexOf(lastImport);
        const insertIndex = lastImportIndex + lastImport.length;
        
        // Add Logger import after the last import
        const loggerImport = "\nimport Logger from '../utils/logger';\n";
        content = content.slice(0, insertIndex) + loggerImport + content.slice(insertIndex);
        console.log(`  ✓ Added Logger import`);
      } else {
        // No imports found, add at the top
        const firstLine = content.split('\n')[0];
        if (firstLine.startsWith('import') || firstLine.startsWith('const') || firstLine.startsWith('function')) {
          content = "import Logger from '../utils/logger';\n" + content;
        } else {
          content = "import Logger from '../utils/logger';\n\n" + content;
        }
        console.log(`  ✓ Added Logger import at top`);
      }
    }
    
    // Write the modified content back
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf8');
      return true;
    }
    
    return false;
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return false;
  }
}

// Main execution
console.log('🔄 Starting console.log replacement...\n');

const files = getAllFiles(srcDir, fileExtensions);
let processedFiles = 0;
let modifiedFiles = 0;

console.log(`Found ${files.length} files to process:\n`);

for (const file of files) {
  console.log(`Processing: ${path.relative(srcDir, file)}`);
  
  if (replaceConsoleInFile(file)) {
    modifiedFiles++;
    console.log(`  ✅ Modified`);
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
  console.log(`\n✅ Console statements successfully replaced with Logger utility!`);
  console.log(`\nNext steps:`);
  console.log(`  1. Run: npm run lint:fix`);
  console.log(`  2. Run: npm run format`);
  console.log(`  3. Test the application to ensure everything works`);
} else {
  console.log(`\nℹ️  No console statements found to replace.`);
}

console.log(`\n🎉 Console replacement complete!`);
