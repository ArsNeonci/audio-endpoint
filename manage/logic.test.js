// node manage/logic.test.js
const assert = require("assert");
const L = require("./logic.js");
const vn = (y, m, d, h = 0, mi = 0, s = 0) => Date.UTC(y, m - 1, d, h, mi, s) - 7 * 3600 * 1000;
const iso = (t) => new Date(t).toISOString().replace(/\.\d{3}Z$/, "Z");

// Paying on the 15th of December extends to 16 January 23:59:59 Vietnam time.
assert.equal(L.extend(iso(vn(2026, 12, 16, 23, 59, 59)), vn(2026, 12, 15, 9), 1), iso(vn(2027, 1, 16, 23, 59, 59)));
// A new month from a date still ahead keeps counting from that date (paying early loses nothing).
assert.equal(L.extend(iso(vn(2027, 1, 16, 23, 59, 59)), vn(2026, 12, 2), 1), iso(vn(2027, 2, 16, 23, 59, 59)));
// Three months at once.
assert.equal(L.extend(iso(vn(2026, 12, 16, 23, 59, 59)), vn(2026, 12, 15), 3), iso(vn(2027, 3, 16, 23, 59, 59)));
// A locked device (date passed) paying on 20 December opens until 16 January, not 16 December.
assert.equal(L.extend(iso(vn(2026, 12, 16, 23, 59, 59)), vn(2026, 12, 20, 10), 1), iso(vn(2027, 1, 16, 23, 59, 59)));
// The 16th itself before midnight is still the current month; just after midnight Vietnam time it is the next.
assert.equal(L.nextLock(vn(2026, 12, 16, 23, 0)), vn(2026, 12, 16, 23, 59, 59));
assert.equal(L.nextLock(vn(2026, 12, 17, 0, 0, 1)), vn(2027, 1, 16, 23, 59, 59));
// A lock day past the end of a short month falls on its last day.
assert.equal(L.nextLock(vn(2027, 2, 1), 31), vn(2027, 2, 28, 23, 59, 59));
// Codes as customers paste them.
assert.equal(L.cleanCode("3FA9-1C2B 7D10-4E5A"), "3fa91c2b7d104e5a");
assert.throws(() => L.cleanCode("3fa9"));
// The public file has codes and dates only.
const file = L.statusFile({message: "m", customers: [{name: "Nguyễn A", contact: "zalo", devices: [{code: "3fa91c2b7d104e5a", valid_until: "2027-01-16T16:59:59Z"}]}]}, 3, vn(2026, 12, 15));
assert.deepEqual(Object.keys(file).sort(), ["devices", "message", "serial", "strict", "updated"]);
assert.ok(!JSON.stringify(file).includes("Nguyễn") && !JSON.stringify(file).includes("zalo"));
assert.equal(file.devices["3fa91c2b7d104e5a"], "2027-01-16T16:59:59Z");
// States as the app computes them.
assert.equal(L.state("2027-01-16T16:59:59Z", vn(2027, 1, 12)), "DUE_SOON");
assert.equal(L.state("2027-01-16T16:59:59Z", vn(2027, 1, 17)), "OVERDUE");
assert.equal(L.state(L.lockNow(vn(2027, 1, 5)), vn(2027, 1, 5)), "OVERDUE");
console.log("logic: all checks passed");
