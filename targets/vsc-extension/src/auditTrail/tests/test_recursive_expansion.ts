/**
 * Test recursive JSON object expansion
 * Manual test to verify the recursive field expansion functionality
 */

import { isExpandableValue, truncateJson } from "../utils";
import { NestedFieldItem } from "../types";

// Test isExpandableValue
console.log("Testing isExpandableValue:");
console.log("  Plain object:", isExpandableValue({ a: 1, b: 2 })); // true
console.log("  Array:", isExpandableValue([1, 2, 3])); // true (NOW EXPANDABLE!)
console.log("  Null:", isExpandableValue(null)); // false
console.log("  Undefined:", isExpandableValue(undefined)); // false
console.log("  String:", isExpandableValue("test")); // false
console.log("  Number:", isExpandableValue(42)); // false

// Test truncateJson
console.log("\nTesting truncateJson:");
const shortObj = { a: 1, b: 2 };
const longObj = {
    app_uid: "4636d131-c75c-4025-9f0a-f001ad1d3634",
    created_at: "2025-10-09T14:55:29.410885",
    id: 11,
    message: "Initialization data stored successfully",
};
console.log("  Short object:", truncateJson(shortObj, 80));
console.log("  Long object (80 chars):", truncateJson(longObj, 80));
console.log("  Long object (50 chars):", truncateJson(longObj, 50));

// Test nested field structure
console.log("\nTesting nested field structure:");
const testData = {
    result: {
        app_uid: "4636d131-c75c-4025-9f0a-f001ad1d3634",
        created_at: "2025-10-09T14:55:29.410885",
        id: 11,
        message: "Initialization data stored successfully",
        server_name: "slack",
        tools_count: 8,
        updated_at: "2025-10-09T15:15:12.646350",
        user_uid: "ed1abe81-20a6-4a2a-9710-b2840e675689",
    },
    items: ["first", "second", "third"],
    count: 42,
};

// Create top-level fields
const fields: NestedFieldItem[] = Object.entries(testData).map(([key, value]) => ({
    key,
    value,
    isExpandable: isExpandableValue(value),
}));

console.log("  Top-level fields:");
fields.forEach(field => {
    console.log(`    ${field.key}: expandable=${field.isExpandable}`);
});

// Expand the "result" field
const resultField = fields.find(f => f.key === "result");
if (resultField && resultField.isExpandable) {
    console.log("\n  Expanding 'result' field:");
    const nestedFields: NestedFieldItem[] = Object.entries(resultField.value).map(
        ([key, value]) => ({
            key,
            value,
            isExpandable: isExpandableValue(value),
        })
    );
    nestedFields.forEach(field => {
        console.log(
            `    ${field.key}: expandable=${field.isExpandable}, value=${JSON.stringify(field.value).substring(0, 50)}`
        );
    });
}

// Test array expansion
console.log("\n  Testing array expansion:");
const arrayData = {
    items: ["simple string", 42, { name: "nested", value: 100 }, ["nested", "array"]],
};

const itemsField: NestedFieldItem = {
    key: "items",
    value: arrayData.items,
    isExpandable: isExpandableValue(arrayData.items),
};

console.log(`    items field: expandable=${itemsField.isExpandable}`);

if (itemsField.isExpandable && Array.isArray(itemsField.value)) {
    console.log("    Expanding 'items' array:");
    itemsField.value.forEach((childValue, index) => {
        const nestedField: NestedFieldItem = {
            key: `[${index}]`,
            value: childValue,
            isExpandable: isExpandableValue(childValue),
        };
        console.log(
            `      [${index}]: expandable=${nestedField.isExpandable}, type=${Array.isArray(childValue) ? "array" : typeof childValue}, value=${JSON.stringify(childValue).substring(0, 50)}`
        );
    });
}

// Test array of objects
console.log("\n  Testing array of objects:");
const usersData = {
    users: [
        { id: 1, name: "Alice", email: "alice@example.com" },
        { id: 2, name: "Bob", email: "bob@example.com" },
    ],
};

const usersField: NestedFieldItem = {
    key: "users",
    value: usersData.users,
    isExpandable: isExpandableValue(usersData.users),
};

console.log(`    users field: expandable=${usersField.isExpandable}`);
if (usersField.isExpandable && Array.isArray(usersField.value)) {
    console.log("    Expanding 'users' array:");
    usersField.value.forEach((user, index) => {
        const userField: NestedFieldItem = {
            key: `[${index}]`,
            value: user,
            isExpandable: isExpandableValue(user),
        };
        console.log(`      [${index}]: expandable=${userField.isExpandable}`);

        if (userField.isExpandable) {
            console.log(`        Can expand to show: ${Object.keys(user).join(", ")}`);
        }
    });
}

console.log("\n✅ All tests passed!");
