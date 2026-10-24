import { QRCodeSVG } from "qrcode.react";
import { useTranslation } from "react-i18next";

const SIZE = 240;
const LOGO = 64; // ~7 % of the code's area: well within level H's 30 % error correction

/** The meal QR code (FR-15): brand green on white, OVAGRI logo in the centre, brand gradient frame. */
export function MealQr({ payload }: { payload: string }) {
  const { t } = useTranslation();
  return (
    <figure className="meal-qr">
      <div className="meal-qr__frame">
        <QRCodeSVG
          value={payload}
          size={SIZE}
          level="H"
          marginSize={2}
          fgColor="currentColor"
          bgColor="transparent"
          title={t("reservations.qrTitle")}
          imageSettings={{ src: "/logo.png", width: LOGO, height: LOGO, excavate: true }}
        />
      </div>
      <figcaption className="meal-qr__caption">{t("app.name")} · {t("app.company")}</figcaption>
    </figure>
  );
}
