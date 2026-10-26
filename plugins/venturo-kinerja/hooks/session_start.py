"""SessionStart — peringatkan bila snapshot rules kinerja lebih tua dari 14 hari.

Rules basi = plugin bisa menilai dengan aturan yang sudah diganti reviewer
kinerja. Diam bila stack repo tidak dikenali atau rules masih segar.
"""

from _common import emit, guarded, lib, project_dir, supported


def main(event):
    if not supported(project_dir(event), event):
        return
    info = lib.rules_info()
    if not info["stale"]:
        return
    msg = ("venturo-kinerja: snapshot rules review berumur %.0f hari (sync %s, batas %d hari). "
           "Aturan reviewer kinerja mungkin sudah berubah; perbarui plugin "
           "(`claude plugin marketplace update venturo-tools`) atau minta maintainer sync ulang rules."
           % (info["age_days"], info["synced_at"], info["stale_after_days"]))
    emit({"systemMessage": msg,
          "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": msg}})


if __name__ == "__main__":
    guarded(main)
