#!/usr/bin/env node

/** Bundle cross-platform executables for VS Code extension */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PLATFORMS = {
    'win32': {
        target: 'x86_64-pc-windows-gnu',
        executable: 'mcpower-windows.exe',
        pythonExecutable: 'python'
    },
    'darwin': {
        target: 'x86_64-apple-darwin',
        executable: 'mcpower-macos',
        pythonExecutable: 'python3'
    },
    'linux': {
        target: 'x86_64-unknown-linux-gnu',
        executable: 'mcpower-linux',
        pythonExecutable: 'python3'
    }
};

class ExecutableBundler {
    constructor(targetPlatform = null) {
        this.extensionRoot = path.dirname(__dirname);
        this.srcRoot = path.join(path.dirname(path.dirname(this.extensionRoot)), 'src');
        this.outputDir = path.join(this.extensionRoot, 'executables');
        this.targetPlatform = targetPlatform;
    }

    async bundle() {
        console.log('Starting executable bundling...');

        this.ensureDirectory(this.outputDir);

        if (!fs.existsSync(this.srcRoot)) {
            throw new Error(`Source directory not found: ${this.srcRoot}`);
        }

        if (this.targetPlatform) {
            // Bundle for specific platform
            if (!PLATFORMS[this.targetPlatform]) {
                throw new Error(`Unsupported platform: ${this.targetPlatform}. Supported: ${Object.keys(PLATFORMS).join(', ')}`);
            }
            console.log(`\nBundling for ${this.targetPlatform}...`);
            await this.bundlePlatform(this.targetPlatform, PLATFORMS[this.targetPlatform]);
        } else {
            // Bundle for all platforms
            for (const [platform, config] of Object.entries(PLATFORMS)) {
                console.log(`\nBundling for ${platform}...`);
                await this.bundlePlatform(platform, config);
            }
        }

        console.log('\n✅ Executable bundling completed successfully!');
        this.printBundleInfo();
    }

    async bundlePlatform(platform, config) {
        const outputPath = path.join(this.outputDir, config.executable);

        try {
            if (this.hasNuitka()) {
                await this.bundleWithNuitka(platform, config, outputPath);
                return;
            }
            
            throw new Error("Nuitka not found! Please install Nuitka: pip install nuitka");
        } catch (error) {
            console.error(`  ❌ Failed to bundle for ${platform}: ${error.message}`);
            throw error;
        }
    }

    async bundleWithNuitka(platform, config, outputPath) {
        const mainScript = path.join(this.srcRoot, 'main.py');
        
        const venvBinDir = process.platform === 'win32' ? 'Scripts' : 'bin';
        const venvNuitka = path.join(this.srcRoot, '.venv', venvBinDir, 'nuitka');
        const venvNuitkaExe = process.platform === 'win32' ? venvNuitka + '.exe' : venvNuitka;
        
        let nuitkaCmd;
        if (fs.existsSync(venvNuitkaExe)) {
            nuitkaCmd = venvNuitkaExe.includes(' ') ? `"${venvNuitkaExe}"` : venvNuitkaExe;
        } else {
            if (process.platform === 'win32') {
                const venvPython = path.join(this.srcRoot, '.venv', 'Scripts', 'python.exe');
                if (fs.existsSync(venvPython)) {
                    nuitkaCmd = `"${venvPython}" -m nuitka`;
                } else {
                    nuitkaCmd = 'python -m nuitka';
                }
            } else {
                nuitkaCmd = 'nuitka';
            }
        }

        const outputName = path.basename(outputPath, path.extname(outputPath));
        const outputExt = platform === 'win32' ? '.exe' : '';
        
        // Quote paths if they contain spaces (common on Windows)
        const quotePath = (p) => p.includes(' ') ? `"${p}"` : p;
        
        const command = [
            nuitkaCmd,
            '--standalone',
            '--onefile',
            `--output-filename="${outputName}${outputExt}"`,
            `--output-dir="${this.outputDir}"`,
            '--include-module=mcpower_shared',
            '--include-module=_json',
            '--include-module=uuid',
            '--include-module=watchdog.observers',
            '--include-module=watchdog.events',
            '--include-package=fastmcp',
            '--include-package=mcp',
            '--include-package=pydantic',
            '--include-package=watchdog',
            // Exclude problematic CLI modules we don't need
            '--nofollow-import-to=mcp.cli',
            // Performance optimizations
            '--enable-plugin=anti-bloat',
            '--assume-yes-for-downloads',
            // Avoid embedding build paths
            '--file-reference-choice=runtime',
            // Platform-specific flags
            platform === 'win32' ? '--windows-console-mode=force' : '',
            quotePath(mainScript)
        ].filter(arg => arg !== ''); // Remove empty arguments

        console.log(`  Using Nuitka: ${nuitkaCmd}`);
        console.log(`  Platform: ${platform}, process.platform: ${process.platform}`);
        console.log(`  Command args: ${command.length} arguments`);
        
        // Execute Nuitka compilation
        try {
            execSync(command.join(' '), {
                cwd: this.srcRoot,
                stdio: 'inherit',
                maxBuffer: 10 * 1024 * 1024 // 10MB buffer for Nuitka output
            });
        } catch (error) {
            throw new Error(`Nuitka compilation failed: ${error.message}`);
        }
        
        // Nuitka creates the executable with the correct name and extension
        const nuitkaOutput = path.join(this.outputDir, `${outputName}${outputExt}`);
        if (fs.existsSync(nuitkaOutput) && nuitkaOutput !== outputPath) {
            fs.renameSync(nuitkaOutput, outputPath);
        }

        console.log(`  ✅ Bundled: ${outputPath}`);
    }


     hasNuitka() {
        try {
            const venvBinDir = process.platform === 'win32' ? 'Scripts' : 'bin';
            const venvNuitka = path.join(this.srcRoot, '.venv', venvBinDir, 'nuitka');
            const venvNuitkaExe = process.platform === 'win32' ? venvNuitka + '.exe' : venvNuitka;
            
            if (fs.existsSync(venvNuitkaExe)) {
                console.log(`  Found Nuitka in virtual environment: ${venvNuitkaExe}`);
                return true;
            }
            
            if (process.platform === 'win32') {
                const venvPython = path.join(this.srcRoot, '.venv', 'Scripts', 'python.exe');
                if (fs.existsSync(venvPython)) {
                    try {
                        execSync(`"${venvPython}" -m nuitka --version`, { stdio: 'pipe' });
                        console.log(`  Found Nuitka via Python module in virtual environment: ${venvPython}`);
                        return true;
                    } catch (e) {
                        // Continue to fallback
                    }
                }
            }
            
            // Fallback: check global Nuitka
            execSync('nuitka --version', { stdio: 'pipe' });
            console.log('  Using global Nuitka');
            return true;
        } catch (error) {
            console.error('  ❌ Nuitka not found in virtual environment or globally');
            console.error('  💡 Run: cd src && source .venv/bin/activate && pip install nuitka');
            return false;
        }
    }


    ensureDirectory(dirPath) {
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
        }
    }

    copyDirectory(src, dest) {
        if (!fs.existsSync(src)) {
            throw new Error(`Source directory does not exist: ${src}`);
        }
        
        fs.mkdirSync(dest, { recursive: true });
        
        const entries = fs.readdirSync(src, { withFileTypes: true });
        for (const entry of entries) {
            const srcPath = path.join(src, entry.name);
            const destPath = path.join(dest, entry.name);
            
            if (entry.isDirectory()) {
                this.copyDirectory(srcPath, destPath);
            } else {
                fs.copyFileSync(srcPath, destPath);
            }
        }
    }

    removeDirectory(dirPath) {
        if (!fs.existsSync(dirPath)) {
            return;
        }
        
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dirPath, entry.name);
            
            if (entry.isDirectory()) {
                this.removeDirectory(fullPath);
            } else {
                fs.unlinkSync(fullPath);
            }
        }
        
        fs.rmdirSync(dirPath);
    }

    printBundleInfo() {
        console.log('\n📦 Bundle Information:');
        console.log(`Output directory: ${this.outputDir}`);

        if (fs.existsSync(this.outputDir)) {
            const files = fs.readdirSync(this.outputDir);
            files.forEach(file => {
                const filePath = path.join(this.outputDir, file);
                const stats = fs.statSync(filePath);
                const sizeKB = Math.round(stats.size / 1024);
                console.log(`  ${file} (${sizeKB} KB)`);
            });
        }

        console.log('\n📋 Next Steps:');
        console.log('1. Test executables on target platforms');
        console.log('2. Update extension package.json if needed');
        console.log('3. Run "npm run package" to create .vsix file');
    }
}

// Run bundler if called directly
if (require.main === module) {
    const args = process.argv.slice(2);
    const platformArg = args.find(arg => arg.startsWith('--platform='));
    const targetPlatform = platformArg ? platformArg.split('=')[1] : null;
    
    if (args.includes('--help') || args.includes('-h')) {
        console.log(`
Usage: node bundle-executables.js [options]

Options:
  --platform=<platform>  Bundle for specific platform (win32, darwin, linux)
  --help, -h            Show this help message

Examples:
  node bundle-executables.js --platform=darwin    # Bundle for macOS only
  node bundle-executables.js --platform=win32     # Bundle for Windows only
  node bundle-executables.js --platform=linux     # Bundle for Linux only
  node bundle-executables.js                      # Bundle for all platforms

Supported platforms: ${Object.keys(PLATFORMS).join(', ')}
        `);
        process.exit(0);
    }
    
    const bundler = new ExecutableBundler(targetPlatform);
    bundler.bundle().catch(error => {
        console.error('Bundling failed:', error);
        process.exit(1);
    });
}

module.exports = ExecutableBundler;