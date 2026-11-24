// Date rules and file shapes of the paid-until manager (no network here, so it can be tested on its own).
// A month is paid up to 23:59:59 on the lock day (default 16) in Vietnam time (UTC+7). Times are stored as UTC ISO strings.
(function (root) {
  const VN = 7 * 3600 * 1000;
  const CODE = /^[0-9a-f]{16}$/;

  /** The first lock moment (lock day, 23:59:59 Vietnam time) strictly after `after` (ms). */
  function nextLock(after, lockDay = 16) {
    const local = new Date(after + VN);
    let year = local.getUTCFullYear(), month = local.getUTCMonth();
    for (let i = 0; i < 3; i++) {
      const day = Math.min(lockDay, new Date(Date.UTC(year, month + 1, 0)).getUTCDate());
      const at = Date.UTC(year, month, day, 23, 59, 59) - VN;
      if (at > after) return at;
      month += 1;
    }
    throw new Error("unreachable");
  }

  /** Extend by `months` paid months: from the current date if it is still ahead, else from now (a locked device opens again). */
  function extend(current, now, months = 1, lockDay = 16) {
    let at = Math.max(current ? Date.parse(current) : 0, now);
    for (let i = 0; i < months; i++) at = nextLock(at, lockDay);
    return new Date(at).toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  const lockNow = (now) => new Date(now - 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
  const trial = (now, days) => new Date(now + days * 86400000).toISOString().replace(/\.\d{3}Z$/, "Z");

  /** A device code as the app shows it (16 hex characters), from what the customer pasted (dashes, spaces, capitals allowed). */
  function cleanCode(text) {
    const code = String(text || "").toLowerCase().replace(/[^0-9a-f]/g, "");
    if (!CODE.test(code)) throw new Error("Mã thiết bị phải có 16 ký tự 0-9 a-f");
    return code;
  }

  /** The public file the apps read: device codes and dates only, never a name. */
  function statusFile(data, serial, now) {
    const devices = {};
    for (const customer of data.customers || []) for (const device of customer.devices || []) devices[device.code] = device.valid_until;
    return {serial, updated: new Date(now).toISOString().replace(/\.\d{3}Z$/, "Z"), strict: Boolean(data.strict), message: String(data.message || ""), devices};
  }

  function state(validUntil, now, noticeDays = 5) {
    const left = Date.parse(validUntil) - now;
    if (!(left > 0)) return "OVERDUE";
    return left <= noticeDays * 86400000 ? "DUE_SOON" : "OK";
  }

  const api = {nextLock, extend, lockNow, trial, cleanCode, statusFile, state};
  if (typeof module !== "undefined") module.exports = api; else root.PaidLogic = api;
})(this);
