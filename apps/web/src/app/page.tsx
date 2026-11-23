"use client";
import Link from "next/link";
import { useWords } from "@/features/Shell";
import { MarketPrint } from "@/features/MarketPrint";
import { pilot } from "@/content/pilot";

export default function Home() {
  const { t, say, lang, whatsapp, phoneAuth } = useWords();
  return (
    <div className="wrap landing">
      <div className="hero">
        <section>
          <p className="placeTag">
            <span aria-hidden="true">⌖</span>
            {pilot[lang].region}
          </p>
          <h1>{say("Good work, close to home.", "अच्छा काम, घर के पास।")}</h1>
          <p className="lead">
            {say(
              "Find a day’s work or a permanent job in the places you know. Local businesses hire by trade and area.",
              "अपने इलाके में दिहाड़ी या स्थायी नौकरी खोजें। स्थानीय दुकानदार और ठेकेदार हुनर और इलाके के हिसाब से काम देते हैं।",
            )}
          </p>
          <div className="actions">
            {whatsapp && (
              <a className="btn primary" href={whatsapp}>
                {say("Start on WhatsApp", "WhatsApp पर शुरू करें")}
              </a>
            )}
            {phoneAuth && (
              <>
                <Link
                  className={`btn ${whatsapp ? "light" : "primary"}`}
                  href="/login?role=worker"
                >
                  {t("find")}
                </Link>
                <Link className="btn light" href="/login?role=employer">
                  {t("post")}
                </Link>
              </>
            )}
            {!phoneAuth && !whatsapp && (
              <p className="notice">
                {say(
                  "Registration is not open yet.",
                  "पंजीकरण अभी शुरू नहीं हुआ है।",
                )}
              </p>
            )}
          </div>
        </section>
        <figure className="print">
          <MarketPrint />
          <figcaption>
            <span lang="hi">{pilot.hi.district}</span>
            <span>{say("Around the local market", "अपने बाज़ार के पास")}</span>
          </figcaption>
        </figure>
      </div>
      <section className="how">
        <h2>{say("How it works", "कैसे काम करता है")}</h2>
        <ol>
          {[
            [
              say("Start with your number", "मोबाइल नंबर से शुरू करें"),
              !phoneAuth && whatsapp
                ? say(
                    "Open KaamPaas on WhatsApp to get started.",
                    "शुरू करने के लिए WhatsApp पर KaamPaas खोलें।",
                  )
                : phoneAuth
                  ? say(
                      "Receive an SMS code. A shared browser works too.",
                      "SMS कोड पाएं। साझा कंप्यूटर का भी उपयोग कर सकते हैं।",
                    )
                  : say(
                      "Phone registration will open here once it is ready.",
                      "मोबाइल से पंजीकरण शुरू होने पर यहाँ उपलब्ध होगा।",
                    ),
            ],
            [
              say("Choose your work area", "काम का इलाका चुनें"),
              say(
                "Pick your trade and the places you can travel to. No CV needed.",
                "हुनर और आने-जाने के इलाके चुनें। बायोडाटा की ज़रूरत नहीं।",
              ),
            ],
            [
              say("Decide together", "मिलकर काम तय करें"),
              say(
                "Check the pay and dates. Phone details are shared when a worker is selected.",
                "मेहनताना और तारीखें जाँचें। काम तय होने पर ही नंबर साझा होते हैं।",
              ),
            ],
          ].map(([name, info], i) => (
            <li key={i}>
              <span className="num">{i + 1}</span>
              <div>
                <h3>{name}</h3>
                <p>{info}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <aside className="coverage">
        <strong>{say("Where you can find work", "काम कहाँ मिलेगा")}</strong>
        <span>{pilot[lang].coverage}</span>
      </aside>
    </div>
  );
}
