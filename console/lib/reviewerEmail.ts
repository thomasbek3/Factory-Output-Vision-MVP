export type InviteLocale = "en" | "es-419";

type ReviewerInviteEmailInput = {
  displayName: string;
  actionUrl: string;
  expiresAt: string;
  locale: InviteLocale;
  supportEmail: string;
};

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatExpiry(iso: string, locale: InviteLocale) {
  return new Intl.DateTimeFormat(locale === "es-419" ? "es-419" : "en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(iso));
}

export function reviewerInviteEmail(input: ReviewerInviteEmailInput) {
  const spanish = input.locale === "es-419";
  const name = escapeHtml(input.displayName.trim());
  const actionUrl = escapeHtml(input.actionUrl);
  const supportEmail = escapeHtml(input.supportEmail);
  const expiry = escapeHtml(formatExpiry(input.expiresAt, input.locale));
  const subject = spanish
    ? "Tu invitación para revisar videos en FactoryVision"
    : "Your invitation to review videos in FactoryVision";
  const preview = spanish
    ? "Activa tu cuenta, protege tu acceso y completa una práctica corta."
    : "Activate your account, secure it, and complete a short practice.";

  const copy = spanish
    ? {
        greeting: `Hola ${name},`,
        intro:
          "Te invitamos al equipo de revisión de FactoryVision. Tu trabajo será revisar videos cortos de producción y marcar cada pieza terminada.",
        button: "Activar mi cuenta",
        stepsTitle: "Qué pasará después",
        steps: [
          "Protegerás tu cuenta con una aplicación de autenticación.",
          "Verás una explicación y una práctica corta.",
          "Después de aprobar, tu siguiente video aparecerá automáticamente.",
        ],
        expiry: `Este enlace vence el ${expiry}.`,
        safety:
          "FactoryVision nunca te pedirá que envíes tu contraseña ni tus códigos de autenticación por correo, chat o teléfono.",
        fallback: "Si el botón no funciona, abre este enlace:",
        help: `¿Necesitas ayuda? Escribe a ${supportEmail}.`,
        footer: "FactoryVision · Revisión privada de producción",
      }
    : {
        greeting: `Hi ${name},`,
        intro:
          "You have been invited to the FactoryVision review team. Your work will be to review short production videos and mark each completed piece.",
        button: "Activate my account",
        stepsTitle: "What happens next",
        steps: [
          "You will protect your account with an authenticator app.",
          "You will complete a short walkthrough and practice.",
          "After you qualify, your next video will appear automatically.",
        ],
        expiry: `This link expires ${expiry}.`,
        safety:
          "FactoryVision will never ask you to send your password or authentication codes by email, chat, or phone.",
        fallback: "If the button does not work, open this link:",
        help: `Need help? Email ${supportEmail}.`,
        footer: "FactoryVision · Private production review",
      };

  const html = `<!doctype html>
<html lang="${spanish ? "es" : "en"}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <title>${escapeHtml(subject)}</title>
</head>
<body style="margin:0;background:#f2f3f4;color:#16191d;font-family:Arial,Helvetica,sans-serif">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0">${escapeHtml(preview)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f2f3f4">
    <tr><td align="center" style="padding:32px 14px">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #dfe2e5">
        <tr>
          <td style="background:#0e1114;padding:24px 30px">
            <div style="color:#ffffff;font-size:20px;font-weight:700;line-height:1.2">FactoryVision</div>
            <div style="color:#9ea4aa;font-size:12px;line-height:1.5;margin-top:5px">${spanish ? "Equipo de revisión" : "Review team"}</div>
          </td>
        </tr>
        <tr>
          <td style="height:5px;background:#f2762e"></td>
        </tr>
        <tr>
          <td style="padding:34px 30px 30px">
            <div style="font-size:20px;font-weight:700;line-height:1.35">${copy.greeting}</div>
            <p style="font-size:15px;line-height:1.65;margin:16px 0 24px;color:#3d4349">${copy.intro}</p>
            <table role="presentation" cellspacing="0" cellpadding="0">
              <tr>
                <td style="background:#f2762e">
                  <a href="${actionUrl}" style="display:inline-block;padding:14px 22px;color:#111111;text-decoration:none;font-size:15px;font-weight:700">${copy.button}</a>
                </td>
              </tr>
            </table>
            <p style="font-size:12px;line-height:1.5;color:#6b7278;margin:12px 0 28px">${copy.expiry}</p>
            <div style="border-top:1px solid #e5e7e9;padding-top:24px">
              <div style="font-size:13px;font-weight:700;text-transform:uppercase;color:#555d64">${copy.stepsTitle}</div>
              <ol style="padding-left:20px;margin:14px 0 0;color:#3d4349">
                ${copy.steps.map((step) => `<li style="font-size:14px;line-height:1.6;margin:7px 0">${step}</li>`).join("")}
              </ol>
            </div>
            <div style="margin-top:26px;padding:16px;border-left:4px solid #f2762e;background:#fff7f1;color:#3d4349;font-size:13px;line-height:1.55">${copy.safety}</div>
            <p style="font-size:12px;line-height:1.55;color:#6b7278;margin:24px 0 4px">${copy.fallback}</p>
            <p style="font-size:11px;line-height:1.5;word-break:break-all;margin:0"><a href="${actionUrl}" style="color:#ad4c16">${actionUrl}</a></p>
            <p style="font-size:13px;line-height:1.5;margin:24px 0 0;color:#3d4349">${copy.help}</p>
          </td>
        </tr>
        <tr>
          <td style="background:#f7f8f8;border-top:1px solid #e5e7e9;padding:18px 30px;color:#747b81;font-size:11px;line-height:1.5">${copy.footer}</td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;

  const text = [
    copy.greeting,
    "",
    copy.intro,
    "",
    copy.button,
    input.actionUrl,
    copy.expiry,
    "",
    copy.stepsTitle,
    ...copy.steps.map((step, index) => `${index + 1}. ${step}`),
    "",
    copy.safety,
    "",
    copy.help,
  ].join("\n");

  return { subject, html, text };
}
