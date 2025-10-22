#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '../../..');
const extensionRoot = path.resolve(__dirname, '..');
const targetDir = path.join(extensionRoot, 'proxy-bundled');

function shouldExclude(relativePath, fileName) {
    const pathParts = relativePath.split(path.sep);
    
    // Exclude directories named exactly 'test' or 'tests'
    for (const part of pathParts) {
        if (part === 'test' || part === 'tests') {
            return true;
        }
    }
    
    // Exclude files with 'test' in their name
    if (fileName.toLowerCase().includes('test')) {
        return true;
    }
    
    return false;
}

function copyRecursive(src, dest, baseDir) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }
    
    const entries = fs.readdirSync(src, { withFileTypes: true });
    
    for (const entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        const relativePath = path.relative(baseDir, srcPath);
        
        if (shouldExclude(relativePath, entry.name)) {
            console.log(`Excluding: ${relativePath}`);
            continue;
        }
        
        if (entry.isDirectory()) {
            copyRecursive(srcPath, destPath, baseDir);
        } else {
            fs.copyFileSync(srcPath, destPath);
            console.log(`Copied: ${relativePath}`);
        }
    }
}

function rmDirRecursive(dirPath) {
    if (!fs.existsSync(dirPath)) {
        return;
    }
    
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    
    for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isDirectory()) {
            rmDirRecursive(fullPath);
        } else {
            fs.unlinkSync(fullPath);
        }
    }
    
    fs.rmdirSync(dirPath);
}

function main() {
    console.log('Copying Python source to proxy-bundled...');
    
    // Clean target directory
    if (fs.existsSync(targetDir)) {
        rmDirRecursive(targetDir);
    }
    
    fs.mkdirSync(targetDir, { recursive: true });
    
    // Copy src/ directory (excluding test files)
    const srcDir = path.join(repoRoot, 'src');
    const targetSrcDir = path.join(targetDir, 'src');
    copyRecursive(srcDir, targetSrcDir, srcDir);
    
    // Copy pyproject.toml
    const pyprojectSrc = path.join(repoRoot, 'pyproject.toml');
    const pyprojectDest = path.join(targetDir, 'pyproject.toml');
    fs.copyFileSync(pyprojectSrc, pyprojectDest);
    console.log('Copied: pyproject.toml');
    
    // Copy uv.lock
    const uvLockSrc = path.join(repoRoot, 'uv.lock');
    const uvLockDest = path.join(targetDir, 'uv.lock');
    fs.copyFileSync(uvLockSrc, uvLockDest);
    console.log('Copied: uv.lock');
    
    console.log('Python source copy complete.');
}

main();

