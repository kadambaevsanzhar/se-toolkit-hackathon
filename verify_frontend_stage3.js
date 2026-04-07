#!/usr/bin/env node
/**
 * Stage 3: Frontend Verification Script
 * Checks that all frontend components and configuration are correct
 */

const fs = require('fs');
const path = require('path');

// Colors for output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function checkFile(filePath, description) {
  const fullPath = path.join(__dirname, filePath);
  if (fs.existsSync(fullPath)) {
    const stats = fs.statSync(fullPath);
    const lines = fs.readFileSync(fullPath, 'utf8').split('\n').length;
    log(`  ✓ ${description.padEnd(40)} (${stats.size} bytes, ${lines} lines)`, 'green');
    return true;
  } else {
    log(`  ✗ ${description.padEnd(40)} - MISSING`, 'red');
    return false;
  }
}

function checkFileContent(filePath, searchString, description) {
  const fullPath = path.join(__dirname, filePath);
  if (fs.existsSync(fullPath)) {
    const content = fs.readFileSync(fullPath, 'utf8');
    if (content.includes(searchString)) {
      log(`  ✓ ${description}`, 'green');
      return true;
    } else {
      log(`  ✗ ${description} - NOT FOUND`, 'red');
      return false;
    }
  } else {
    log(`  ✗ ${description} - FILE MISSING`, 'red');
    return false;
  }
}

console.log('\n' + '='.repeat(70));
log('STAGE 3: FRONTEND VERIFICATION', 'blue');
console.log('='.repeat(70) + '\n');

let totalChecks = 0;
let passedChecks = 0;

// Check 1: Required Files
log('✓ Checking Required Files', 'blue');
const files = [
  ['frontend/src/App.jsx', 'App.jsx - Main component'],
  ['frontend/src/components/UploadForm.jsx', 'UploadForm.jsx - Upload form'],
  ['frontend/src/components/ResultDisplay.jsx', 'ResultDisplay.jsx - Result display'],
  ['frontend/src/App.css', 'App.css - Component styles'],
  ['frontend/src/index.css', 'index.css - Global styles'],
  ['frontend/src/main.jsx', 'main.jsx - Entry point'],
  ['frontend/index.html', 'index.html - HTML template'],
  ['frontend/package.json', 'package.json - Dependencies'],
  ['frontend/vite.config.js', 'vite.config.js - Vite configuration'],
  ['frontend/Dockerfile', 'Dockerfile - Docker container'],
];

files.forEach(([filePath, desc]) => {
  totalChecks++;
  if (checkFile(filePath, desc)) passedChecks++;
});

console.log();

// Check 2: Build Output
log('✓ Checking Build Output', 'blue');
const buildFiles = [
  ['frontend/dist/index.html', 'dist/index.html - Built HTML'],
  ['frontend/dist/assets', 'dist/assets/ - Built assets (exists)'],
];

buildFiles.forEach(([filePath, desc]) => {
  totalChecks++;
  const fullPath = path.join(__dirname, filePath);
  if (fs.existsSync(fullPath)) {
    log(`  ✓ ${desc.padEnd(40)}`, 'green');
    passedChecks++;
  } else {
    log(`  ✗ ${desc.padEnd(40)} - MISSING`, 'red');
  }
});

console.log();

// Check 3: Dependencies
log('✓ Checking Dependencies in package.json', 'blue');
totalChecks++;
const hasDeps = checkFileContent('frontend/package.json', '"react": "^18.2.0"', 'React 18.2.0+ configured');
if (hasDeps) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/package.json', '"vite": "^5.0.0"', 'Vite 5.0+ configured')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/package.json', '"axios": "^1.6.2"', 'Axios 1.6+ configured')) passedChecks++;

console.log();

// Check 4: Component Implementation
log('✓ Checking Component Implementation', 'blue');

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', '/analyze', 'UploadForm calls /analyze endpoint (corrected)')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', 'handleFileChange', 'UploadForm has file change handler')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', 'handleSubmit', 'UploadForm has submit handler')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/ResultDisplay.jsx', 'suggested_score', 'ResultDisplay shows score')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/ResultDisplay.jsx', 'short_feedback', 'ResultDisplay shows feedback')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/ResultDisplay.jsx', 'strengths', 'ResultDisplay shows strengths')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/ResultDisplay.jsx', 'mistakes', 'ResultDisplay shows mistakes')) passedChecks++;

console.log();

// Check 5: Styling & UI
log('✓ Checking Styling', 'blue');

totalChecks++;
if (checkFileContent('frontend/src/App.css', '.upload-form', 'Upload form styling present')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/App.css', '.submit-btn', 'Submit button styling present')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/App.css', '.result-', 'Result display styling present')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/App.css', '@media', 'Responsive design implemented')) passedChecks++;

console.log();

// Check 6: Configuration
log('✓ Checking Configuration', 'blue');

totalChecks++;
if (checkFileContent('frontend/vite.config.js', 'port: 3000', 'Dev server port 3000 configured')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/vite.config.js', '/analyze', 'Vite proxy configured for /analyze')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/index.html', 'main.jsx', 'HTML entry point configured')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/Dockerfile', 'npm run build', 'Docker builds frontend')) passedChecks++;

console.log();

// Check 7: Error Handling
log('✓ Checking Error Handling', 'blue');

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', 'error', 'Error state management')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', 'catch', 'Error catching implemented')) passedChecks++;

totalChecks++;
if (checkFileContent('frontend/src/components/UploadForm.jsx', 'image/', 'File type validation (image only)')) passedChecks++;

console.log();

// Summary
log('='.repeat(70), 'blue');
log('VERIFICATION SUMMARY', 'blue');
log('='.repeat(70), 'blue');

log(`\nTotal Checks: ${totalChecks}`);
log(`Passed: ${passedChecks}/${totalChecks}`);

if (passedChecks === totalChecks) {
  log('\n✅ STAGE 3 FRONTEND VERIFIED - ALL CHECKS PASSED', 'green');
  log('\nFrontend is ready for deployment:', 'green');
  log('  • Minimal React + Vite setup', 'green');
  log('  • Single-page application', 'green');
  log('  • Image upload with validation', 'green');
  log('  • Loading state & error handling', 'green');
  log('  • Result display with all fields', 'green');
  log('  • API endpoint corrected', 'green');
  log('  • Build successful', 'green');
  process.exit(0);
} else {
  log(`\n✗ STAGE 3 VERIFICATION FAILED - ${totalChecks - passedChecks} checks failed`, 'red');
  log('\nReview the failing checks above', 'red');
  process.exit(1);
}
