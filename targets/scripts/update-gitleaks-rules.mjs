#!/usr/bin/env node
import { writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, "..", "..", "..");
const outputPath = join(projectRoot, "src", "modules", "redaction", "gitleaks_rules.py");

// Download and process Gitleaks rules
async function downloadGitleaksRules() {
    const GITLEAKS_TOML_URL =
        "https://raw.githubusercontent.com/gitleaks/gitleaks/master/config/gitleaks.toml";

    try {
        console.log("📥 Downloading Gitleaks rules...");
        const response = await fetch(GITLEAKS_TOML_URL);
        if (!response.ok) {
            throw new Error(
                `Failed to download: ${response.status} ${response.statusText}`
            );
        }
        return await response.text();
    } catch (err) {
        console.error("❌ Failed to download Gitleaks rules:", err.message);
        console.log("ℹ️  Using manually curated rules instead");
        return null;
    }
}

function parseTomlSimple(tomlContent) {
    // Simple TOML parser for the specific structure we need
    const rules = [];
    const lines = tomlContent.split("\n");
    let currentRule = null;
    let inRule = false;
    let inKeywords = false;

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed === "[[rules]]") {
            // Save previous rule if valid
            if (currentRule && currentRule.id && currentRule.regex) {
                rules.push(currentRule);
            }
            currentRule = { keywords: [] };
            inRule = true;
            inKeywords = false;
        } else if (inRule && currentRule) {
            if (trimmed.startsWith("id = ")) {
                const match = trimmed.match(/id = ["']([^"']+)["']/);
                if (match) currentRule.id = match[1];
                inKeywords = false;
            } else if (trimmed.startsWith("regex = ")) {
                // Handle both single and triple quoted strings
                const tripleMatch = trimmed.match(/regex = '''(.*)'''/);
                const singleMatch = trimmed.match(/regex = ["']([^"']+)["']/);
                if (tripleMatch) {
                    currentRule.regex = tripleMatch[1];
                } else if (singleMatch) {
                    currentRule.regex = singleMatch[1];
                }
                inKeywords = false;
            } else if (trimmed.startsWith("keywords = [")) {
                // Handle start of keywords array
                const keywordsMatch = trimmed.match(/keywords = \[(.*)\]/);
                if (keywordsMatch && keywordsMatch[1].includes("]")) {
                    // Single line keywords
                    const keywordStr = keywordsMatch[1];
                    if (keywordStr.trim()) {
                        currentRule.keywords = keywordStr
                            .split(",")
                            .map(k => k.trim().replace(/["']/g, ""));
                    }
                    inKeywords = false;
                } else {
                    // Multi-line keywords array
                    inKeywords = true;
                    // Check if there's content on the same line
                    const sameLineMatch = trimmed.match(
                        /keywords = \[\s*["']([^"']+)["']/
                    );
                    if (sameLineMatch) {
                        currentRule.keywords.push(sameLineMatch[1]);
                    }
                }
            } else if (inKeywords) {
                if (trimmed === "]") {
                    inKeywords = false;
                } else if (trimmed.includes('"') || trimmed.includes("'")) {
                    // Extract keyword from line
                    const keywordMatch = trimmed.match(/["']([^"']+)["']/);
                    if (keywordMatch) {
                        currentRule.keywords.push(keywordMatch[1]);
                    }
                }
            } else if (trimmed.startsWith("secretGroup = ")) {
                const groupMatch = trimmed.match(/secretGroup = (\d+)/);
                if (groupMatch) {
                    currentRule.secretGroup = parseInt(groupMatch[1]);
                }
            } else if (trimmed.startsWith("[") && !trimmed.startsWith("[[rules]]")) {
                // We've hit a new section, stop processing this rule
                inRule = false;
                inKeywords = false;
            }
        } else if (trimmed.startsWith("[") && !trimmed.startsWith("[[rules]]")) {
            // We've hit a new section
            inRule = false;
            inKeywords = false;
        }
    }

    // Don't forget the last rule
    if (currentRule && currentRule.id && currentRule.regex) {
        rules.push(currentRule);
    }

    return { rules };
}

function processRegexForPython(pattern, rule) {
    let processedPattern = pattern;
    let flags = [];

    // Handle case insensitive flag
    if (rule["regex_case_insensitive"] || processedPattern.includes("(?i)")) {
        flags.push("re.IGNORECASE");
        processedPattern = processedPattern.replace(/\(\?i\)/g, "");
    }

    // Remove other problematic inline flags
    processedPattern = processedPattern.replace(/\(\?-?[imsux]+\)/g, "");
    processedPattern = processedPattern.replace(/\(\?P<[^>]+>/g, "(");

    // Fix character class issues - move hyphens to the end
    processedPattern = processedPattern.replace(
        /\[([^\]]*)-([^\]]*)\]/g,
        (match, before, after) => {
            if (before.includes("=") || after.includes("=")) {
                // Move hyphen to end: [a-z=] becomes [az=-]
                return `[${before.replace(/-/g, "")}${after.replace(/-/g, "")}-]`;
            }
            return match;
        }
    );

    // Fix common problematic patterns
    processedPattern = processedPattern.replace(/\\-=/g, "=-"); // Fix \-= to =-
    processedPattern = processedPattern.replace(/\[([^\]]*)-=([^\]]*)\]/g, "[$1$2=-]"); // Move - to end in char classes

    // Fix Python-incompatible escape sequences
    processedPattern = processedPattern.replace(/\\z/g, "$"); // \z -> $ (end of string)
    processedPattern = processedPattern.replace(/\\B/g, ""); // Remove \B (not word boundary) - problematic in some contexts

    const flagsExpr = flags.length > 0 ? flags.join(" | ") : "0";
    return { pattern: processedPattern, flags: flagsExpr };
}

function pythonRawLiteral(str) {
    // For raw strings, we only need to escape single quotes
    // Backslashes should NOT be doubled in raw strings
    const escaped = str.replace(/'/g, "\\'");
    return `r'${escaped}'`;
}

function escapePythonString(str) {
    return str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

async function updateGitleaksRules() {
    const tomlContent = await downloadGitleaksRules();

    if (!tomlContent) {
        console.log("ℹ️  Keeping existing manually curated rules");
        return;
    }

    try {
        console.log("🔄 Parsing Gitleaks rules...");
        const parsed = parseTomlSimple(tomlContent);
        const rules = parsed.rules || [];

        const pythonRules = [];
        const validRules = [];

        console.log(`📋 Processing ${rules.length} rules...`);

        rules.forEach((rule, idx) => {
            if (!rule.regex || !rule.id) return;

            const { pattern, flags } = processRegexForPython(rule.regex, rule);

            // Test if the pattern can be compiled
            try {
                new RegExp(pattern, flags.includes("re.IGNORECASE") ? "i" : "");
                // Skip rules with problematic patterns
                if (
                    pattern.includes("(?-i:") ||
                    pattern.includes("(?P<") ||
                    pattern.includes("[09az--]") ||
                    pattern.includes("[azAZ09---]") ||
                    pattern.includes("\\-=") ||
                    pattern.includes("-=") ||
                    pattern.includes("\\z") ||
                    pattern.includes("\\B") ||
                    /\[[^\]]*-[^\]]*=[^\]]*\]/.test(pattern)
                ) {
                    console.log(
                        `⚠️  Skipping problematic rule: ${rule.id} (pattern: ${pattern.substring(0, 50)}...)`
                    );
                    return;
                }
                validRules.push({
                    id: rule.id,
                    pattern,
                    flags,
                    secretGroup: rule.secretGroup || 1, // Default to group 1 for the captured secret
                    keywords: (rule.keywords || []).map(k => k.toLowerCase()),
                });
            } catch (err) {
                console.log(
                    `⚠️  Skipping invalid regex rule: ${rule.id} (${err.message})`
                );
                return;
            }
        });

        console.log(`✅ Validated ${validRules.length} working rules`);

        // Add manual rule overrides
        const manualRules = [
            {
                id: "aws-secret-access-key",
                pattern:
                    "(?:[\\w.-]{0,50}?(?:aws|secret)(?:[ \\t\\w.-]{0,20})[\\s'\"]{0,3}(?:=|>|:{1,3}=|\\|\\||:|=>|\\?=|,)[\\x60'\"\\s=]{0,5})?([A-Za-z0-9+/]{40})(?:[\\x60'\"\\s;]|\\\\[nr]|$)",
                flags: "re.IGNORECASE",
                secretGroup: 1,
                keywords: ["aws", "secret"],
            },
            {
                id: "database-password",
                pattern: "://[^:/@]+:([^:/@]{6,})@",
                flags: "0",
                secretGroup: 1,
                keywords: ["://"],
            },
            {
                id: "gcp-api-key",
                pattern: "\\b(AIza[\\w-]{33,35})(?:[\\x60'\"\\s;]|\\\\[nr]|$)",
                flags: "0",
                secretGroup: 1,
                keywords: ["aiza"],
            },
            {
                id: "sendgrid-api-token",
                pattern: "\\b(SG\\.[a-z0-9=_.\\-]{66})(?:[\\x60'\"\\s;]|\\\\[nr]|$)",
                flags: "re.IGNORECASE",
                secretGroup: 1,
                keywords: ["sg."],
            },
        ];

        // Add manual rules with ii suffix if name conflicts
        manualRules.forEach(manualRule => {
            const existingIndex = validRules.findIndex(r => r.id === manualRule.id);
            if (existingIndex >= 0) {
                // Generate a simple ii suffix
                manualRule.id = `${manualRule.id}-ii`;
                console.log(`➕ Added manual rule with UUID: ${manualRule.id}`);
            } else {
                console.log(`➕ Added manual rule: ${manualRule.id}`);
            }
            validRules.push(manualRule);
        });

        // Generate Python file
        const pythonLines = [];
        pythonLines.push("import re");
        pythonLines.push("from typing import Dict, List, Tuple");
        pythonLines.push("");
        pythonLines.push(
            "# This file is auto-generated from Gitleaks rules. Do not edit manually."
        );
        pythonLines.push(
            "# Source: https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml"
        );
        pythonLines.push(
            "# Generation script: targets/scripts/update-gitleaks-rules.mjs"
        );
        pythonLines.push("");
        pythonLines.push(
            "COMPILED_RULES: List[Tuple[str, re.Pattern, int, List[str]]] = ["
        );

        validRules.forEach(rule => {
            const patternLiteral = pythonRawLiteral(rule.pattern);
            const keywordsStr = rule.keywords.length
                ? "[" +
                  rule.keywords.map(k => `"${escapePythonString(k)}"`).join(", ") +
                  "]"
                : "[]";

            pythonLines.push("    (");
            pythonLines.push(`        "${escapePythonString(rule.id)}",`);
            pythonLines.push(`        re.compile(${patternLiteral}, ${rule.flags}),`);
            pythonLines.push(`        ${rule.secretGroup},`);
            pythonLines.push(`        ${keywordsStr},`);
            pythonLines.push("    ),");
        });

        pythonLines.push("]");
        pythonLines.push("");
        pythonLines.push("KEYWORD_INDEX: Dict[str, List[int]] = {}");
        pythonLines.push("for idx, (_, _, _, keywords) in enumerate(COMPILED_RULES):");
        pythonLines.push("    for kw in keywords:");
        pythonLines.push("        KEYWORD_INDEX.setdefault(kw, []).append(idx)");
        pythonLines.push("");
        pythonLines.push(
            'ALWAYS_RUN_IDS = {"jwt", "generic-api-key", "aws-access-token", "aws-secret-access-key", "simple-secret"}'
        );
        pythonLines.push("");
        pythonLines.push("def candidate_rule_indices(text_lower: str) -> List[int]:");
        pythonLines.push("    hits: List[int] = []");
        pythonLines.push("    seen = set()");
        pythonLines.push("    for kw, indices in KEYWORD_INDEX.items():");
        pythonLines.push("        if kw and kw in text_lower:");
        pythonLines.push("            for i in indices:");
        pythonLines.push("                if i not in seen:");
        pythonLines.push("                    hits.append(i)");
        pythonLines.push("                    seen.add(i)");
        pythonLines.push("    for i, (rid, _, _, _) in enumerate(COMPILED_RULES):");
        pythonLines.push("        if rid in ALWAYS_RUN_IDS and i not in seen:");
        pythonLines.push("            hits.append(i)");
        pythonLines.push("            seen.add(i)");
        pythonLines.push("    return hits");
        pythonLines.push("");

        writeFileSync(outputPath, pythonLines.join("\n") + "\n", "utf8");
        console.log(`✅ Updated ${outputPath} with ${validRules.length} rules`);
    } catch (err) {
        console.error("❌ Failed to process Gitleaks rules:", err.message);
        console.log("ℹ️  Keeping existing manually curated rules");
    }
}

// Run the update
updateGitleaksRules().catch(err => {
    console.error("❌ Script failed:", err);
    process.exit(1);
});
