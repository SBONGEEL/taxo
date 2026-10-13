"""نشرُ سياسات الجزائر وشروطها بأمر المالك (SPEC §٧٤-ل/١) — **النصُّ كما صِيغ في المسوّدة، بالعربيّة والفرنسيّة**.

    docker compose … run --rm --no-deps backend python -m scripts.algeria_policies_74 [--apply]

## ما يتغيّر عن المسوّدة — **ثلاثةٌ لا غير، وكلُّها تُقال في التقرير**

١. **وسمُ «— مسوّدة» في سطر العنوان يُنزع** — الوثيقةُ صارت منشورة.
٢. **ملاحظاتُ «[يحتاج مراجعة قانونية: …]» تُنزع من النصّ المنشور** — كانت أسئلةً للمحامي لا كلاماً للراكب والكبتن؛ **وتُسلَّم للمالك قائمةً**
   (`LEGAL_NOTES` أدناه تُطبع في المعاينة) فلا يضيع ما سألت عنه.
٣. **بندُ اللغة في شروط الراكب** يقول ما صار واقعاً: الشروطُ والتطبيقُ بالعربيّة والفرنسيّة.

**والفرنسيُّ ترجمةُ النصّ العربيّ المنشور حرفاً بحرف** (بلا زيادة)، وأرقامُ الأقسام وبنودُها كما هي فتُخبز صفحاتُها بالشكل نفسِه.

## وحرّاسُه

* **نسخةٌ جديدةٌ تُكتب ثمّ تُنشر ببابيهما** (`policies.create_version` · `policies.publish`) **بلا فاعل** — المالكُ قرّر في المحادثة،
  **وسطرُ التدقيق يكتب الأمر**. **ولا تُوسَم «تغييراً جوهرياً»**: لا أحدَ في الجزائر وافق على شيءٍ قبلها.
* **وإعادتُه لا تكتب شيئاً** إن كان المنشورُ هو هذا النصّ حرفاً. **ومعاينةٌ افتراضاً، ومعاملةٌ واحدة.**
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType  # noqa: E402
from app.services import audit  # noqa: E402
from app.services import policies as policies_service  # noqa: E402
from scripts import seed_policies  # noqa: E402

COUNTRY = CountryCode.DZ
REASON = "أمرُ المالك ٢٠٢٦-١٠-١٣: «publish the four Algeria policies exactly as you drafted them, in Arabic and French» (SPEC §٧٤-ل/١)"
_NOTE = re.compile(r"\s*\[يحتاج\s+مراجعة\s+قانونية[^\]]*\]", re.DOTALL)
_DRAFT_TITLE = " — مسوّدة"
_LANG_OLD = "تُتاح هذه الشروطُ بالعربية، والتطبيقُ بالعربية والفرنسية."
_LANG_NEW = "تُتاح هذه الشروطُ والتطبيقُ بالعربية والفرنسية."


def legal_notes(body: str) -> list[str]:
    return [" ".join(m.group(0).split()).strip() for m in _NOTE.finditer(body)]


def publishable(body: str) -> str:
    """**المسوّدةُ كما هي** بلا وسم المسوّدة ولا ملاحظات المحامي — والأسطرُ والأقسامُ كما كُتبت."""
    lines = body.strip().split("\n")
    lines[0] = lines[0].replace(_DRAFT_TITLE, "")
    text = _NOTE.sub("", "\n".join(lines))
    text = text.replace(_LANG_OLD, _LANG_NEW)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


FR_RIDER_PRIVACY = """Politique de confidentialité — application passager (Algérie)

Ce document décrit ce que l'application collecte réellement aujourd'hui, pourquoi elle le collecte, qui y a accès et quand
c'est effacé. Il est rédigé à partir du fonctionnement réel du système, et non de modèles génériques.

1) Qui nous sommes et comment nous joindre
Le service est exploité par l'entité indiquée dans la rubrique « Entité » de l'application ; les questions relatives à la vie
privée et les demandes concernant vos données sont à adresser à l'adresse e-mail de confidentialité publiée à cet endroit.

2) La loi que nous appliquons
Nous traitons vos données à caractère personnel conformément à la loi algérienne relative à la protection des personnes
physiques dans le traitement des données à caractère personnel (loi 18-07, telle que modifiée par la loi 25-11).

3) Ce que nous collectons
- Votre numéro de téléphone, votre nom et votre pays — c'est avec eux que le compte est créé, et le numéro est votre
  identifiant chez nous.
- Votre adresse e-mail si vous l'ajoutez — un canal alternatif, demandé par certains prestataires lorsque vous payez par carte.
- Votre sexe si vous le déclarez vous-même — il n'est pas demandé et ne sert qu'à un service que vous choisissez.
- Les lieux de vos courses : point de départ, destination et arrêts intermédiaires.
- Le trajet de la course pendant son déroulement — des points relevés environ toutes les vingt secondes.
- Ce qui concerne le paiement : les mouvements de votre portefeuille, les demandes de paiement que vous envoyez avec la photo
  du reçu et le numéro du virement lorsque vous payez par virement (BaridiMob, CCP ou compte bancaire), et le numéro de série
  de la carte TAXO que vous utilisez.
- Vos notes et commentaires sur les courses, et la langue d'application que vous choisissez.
- L'identifiant de votre appareil et le jeton de notifications — pour vous envoyer les notifications de votre course.

4) Ce que nous ne collectons pas et ne conservons pas
Nous ne conservons en aucun cas le numéro de votre carte bancaire (EDAHABIA ou CIB) ni son code secret : le paiement par
carte passe par la page du prestataire (Chargily ou SofizPay), et nous n'en recevons que la preuve que le paiement a été
effectué et son montant. Le code de la carte TAXO n'est pas conservé en clair — nous conservons son empreinte, dont il ne
peut être déduit.

5) Pourquoi nous collectons la position
Votre position au moment de la demande sert à trouver un capitaine à proximité. Le trajet de la course sert à deux choses :
calculer la distance réelle sur laquelle repose le tarif final, et prouver ce qui s'est passé en cas de litige sur une
course. Nous ne suivons pas votre position lorsque vous n'êtes pas en course.

6) Qui voit quoi
- Le capitaine affecté à votre course voit votre prénom, le lieu de prise en charge et votre destination.
- L'équipe financière voit la demande de paiement et la photo de son reçu, pour l'approuver ou la refuser avec un motif écrit.
- L'équipe d'assistance voit l'historique de vos courses et de leurs paiements, pour traiter une réclamation.
- La consultation de votre nom associé à votre position en temps réel est réservée au seul propriétaire du compte
  d'administration, et chaque ouverture de cet écran est enregistrée au nom de la personne qui l'a ouvert.

7) Les prestataires par lesquels passent vos données
- Mapbox — cartes et calcul des itinéraires routiers : il reçoit les coordonnées des points de votre course.
- Le prestataire des messages de vérification — il reçoit votre numéro de téléphone et le code de vérification, rien d'autre.
- Firebase Cloud Messaging — notifications : il reçoit le jeton de votre appareil et le texte de la notification.
- Chargily et SofizPay — lorsque vous choisissez de payer par carte par leur intermédiaire : ils reçoivent le montant, votre
  nom, votre numéro de téléphone et votre e-mail lorsqu'ils le demandent.
Seul ce qui est nécessaire à leur mission est transmis à chacun d'eux.

8) Durée de conservation
Votre compte, l'historique de vos courses, le registre de votre portefeuille et vos demandes de paiement sont conservés tant
que votre compte existe ; ils constituent un registre financier et une preuve en cas de litige. La suspension du compte n'en
est pas l'effacement.

9) Vos droits
Être informé de ce que nous traitons, accéder à ce que nous détenons sur vous, en demander la rectification, et vous opposer
à un traitement qui n'est pas nécessaire au fonctionnement du service — comme les notifications d'offres, que vous pouvez
désactiver dans les réglages de l'application. Vous pouvez également adresser une réclamation à l'Autorité nationale de
protection des données à caractère personnel.

10) Modification de cette politique
En cas de modification substantielle, il vous sera demandé de l'accepter à nouveau avant de poursuivre l'utilisation. Les
corrections de forme ne vous redemandent rien.
"""

FR_RIDER_TERMS = """Conditions d'utilisation — application passager (Algérie)

Ce document décrit la relation entre vous et la plateforme telle que le système fonctionne aujourd'hui en Algérie.

1) Ce service
Une plateforme qui met en relation un passager et un capitaine indépendant qui conduit son propre véhicule. Ce que nous
fournissons : la mise en relation, la tarification, l'encaissement et la tenue du registre.

2) Votre compte
Un seul compte par numéro de téléphone, utilisé uniquement à votre connaissance. Le numéro est vérifié par un code qui vous
est envoyé avant la fin de l'inscription.

3) Monnaie et tarif
Tous les montants sont en dinars algériens, sans centimes. Le tarif est calculé sur nos serveurs, et non dans votre
application : un montant de base, une distance et une durée, aux prix annoncés pour votre marché au moment de la demande. Le
tarif peut être recalculé lors du décompte final si le trajet réel diffère de l'estimation.

4) Annulation
Annuler une demande avant son acceptation ne vous coûte rien. Après que le capitaine l'a acceptée et s'est mis en route vers
vous, des frais d'annulation peuvent être dus ; ils vous sont présentés avant d'être prélevés.

5) Paiement
- En espèces au capitaine.
- Depuis votre portefeuille, rechargé par l'un des moyens annoncés dans votre marché :
  · virement via BaridiMob, vers un compte CCP ou un compte bancaire — vous envoyez la photo du reçu et le numéro du virement,
    et l'équipe financière l'approuve ou le refuse avec un motif écrit ; le montant n'est pas ajouté avant l'approbation, et
    un même virement n'est jamais compté deux fois.
  · en espèces dans une agence TAXO s'il en existe une dans votre ville.
  · carte TAXO — un code imprimé utilisable une seule fois.
  · carte bancaire (EDAHABIA ou CIB) via la page de Chargily ou de SofizPay — le montant est ajouté lorsque le prestataire
    confirme le paiement. Les frais du prestataire sont à la charge de la plateforme, sauf indication contraire annoncée
    avant le paiement.
- Le solde de votre portefeuille sert à payer ; il ne peut pas être retiré en espèces.

6) Cartes TAXO
Elles sont vendues dans des commerces agréés ; chacune porte une valeur et une durée de validité imprimées. Son code est
ajouté à votre portefeuille une seule fois ; il ne fonctionne ni avant le début de sa validité ni après son expiration, ni si
la carte a été annulée avant son utilisation. Une personne qui saisit des codes erronés à répétition est temporairement bloquée.

7) Litige sur un paiement
Vous pouvez ouvrir un litige sur un paiement depuis l'historique de vos courses ; il est tranché depuis le panneau
d'administration sur la base du trajet de la course et du registre des paiements.

8) Comportement attendu
Respect du capitaine et de son véhicule, et aucune utilisation du service contraire à la loi. Le compte peut être suspendu en
cas de plaintes répétées, et les obligations financières qui s'y rattachent demeurent.

9) Notre responsabilité
Nous veillons à ce que le service soit disponible et que ses calculs soient exacts ; nous ne garantissons pas la
disponibilité d'un capitaine à tout moment et en tout lieu.

10) Langue
Ces conditions et l'application sont disponibles en arabe et en français.

11) Modification des conditions
La nouvelle version est publiée dans l'application, et son acceptation est demandée si la modification est substantielle.
"""

FR_DRIVER_PRIVACY = """Politique de confidentialité — application capitaine (Algérie)

Ce document décrit ce que l'application collecte auprès de vous en tant que capitaine ; c'est plus large que ce qui est
collecté auprès du passager, car votre activité l'exige.

1) Qui nous sommes et comment nous joindre
L'entité indiquée dans la rubrique « Entité » de l'application, et l'adresse e-mail de confidentialité qui y est publiée.
Nous traitons vos données conformément à la loi algérienne relative à la protection des données à caractère personnel
(loi 18-07, telle que modifiée par la loi 25-11).

2) Ce que nous collectons
- Votre numéro de téléphone, votre nom et votre pays, ainsi que votre sexe lorsqu'il est nécessaire au service réservé aux femmes.
- Vos documents : permis de conduire, pièce d'identité, carte grise du véhicule, assurance, et une photo personnelle
  lorsqu'elle est demandée.
- Les données de votre véhicule : marque, modèle, année, couleur et numéro d'immatriculation.
- Votre position pendant que vous êtes connecté au service, et le trajet de chaque course que vous effectuez.
- Les mouvements de votre portefeuille, vos abonnements et vos avances, ainsi que vos demandes de paiement avec leurs reçus.
- La destination du retrait de vos gains : numéro CCP et sa clé, RIP BaridiMob ou RIB de votre compte bancaire, et le nom du
  titulaire du compte — inscrits avec chaque demande de retrait et conservés avec elle.
- Les notes que vous attribuent les passagers, l'identifiant de votre appareil et le jeton de notifications, et la langue de
  l'application.

3) Pourquoi nous collectons la position
Votre position pendant la connexion sert à vous proposer les courses à proximité et à afficher votre voiture sur la carte du
passager, sans votre nom. Le trajet de la course sert à calculer la distance réelle et à trancher les litiges. Lorsque vous
vous déconnectez, la diffusion s'arrête.

4) Vos documents, la destination de vos retraits et qui les voit
Vos documents sont téléversés sur nos serveurs et examinés depuis le panneau d'administration pour votre validation ; ils ne
sont montrés à aucun passager. La destination de vos retraits n'est visible que par l'agent financier qui traite votre demande.

5) Ce que voit le passager
Votre nom, votre note, l'immatriculation et la marque de votre véhicule après que vous avez accepté sa course, ainsi que la
position de votre voiture pendant que vous vous dirigez vers lui. Avant l'acceptation, il ne voit qu'une voiture sur la carte,
sans nom.

6) Les prestataires
Comme dans la politique du passager : les cartes, les messages de vérification, les notifications, et les deux prestataires
de paiement lorsque vous payez par carte.

7) Durée de conservation
L'historique de vos courses, le registre de votre portefeuille, vos documents de validation et vos demandes de retrait sont
conservés tant que votre compte existe ; ils constituent un registre financier et une preuve en cas de litige.

8) Vos droits
Être informé, accéder, demander la rectification, vous opposer à ce qui n'est pas nécessaire au fonctionnement du service, et
adresser une réclamation à l'Autorité nationale de protection des données à caractère personnel.

9) Modification de cette politique
Toute modification substantielle doit être acceptée à nouveau avant de poursuivre votre activité.
"""

FR_DRIVER_TERMS = """Conditions d'utilisation — application capitaine (Algérie)

Ce document décrit la relation de travail entre vous et la plateforme telle que le système fonctionne aujourd'hui en Algérie.

1) Votre statut
Vous travaillez pour votre propre compte avec votre véhicule ; vous n'êtes pas notre salarié. Vous êtes responsable de votre
permis, de votre assurance, de vos obligations fiscales et sociales et de l'entretien de votre véhicule.

2) La validation
Aucune course ne vous parvient avant la validation de votre compte ; la validation exige un numéro de téléphone vérifié et des
documents acceptés. Le téléversement d'un nouveau document requis ou la modification de l'identité de votre véhicule vous
remet en examen.

3) L'abonnement
Travailler sur la plateforme exige un abonnement en cours de validité ; à son expiration, vous ne recevez plus d'offres de
courses. L'abonnement se paie depuis votre portefeuille, par virement (BaridiMob, CCP ou compte bancaire) approuvé par
l'équipe financière, en espèces dans une agence TAXO, ou par carte via le prestataire de paiement. Le renouvellement commence
à la fin de la période en cours, et non au jour du paiement.

4) Monnaie et commission
Tous les montants sont en dinars algériens, sans centimes. La commission de la plateforme est calculée au taux annoncé et
figée au moment où vous acceptez la course. Pour les courses dont vous encaissez le prix vous-même, la commission reste une
dette à votre charge, prélevée sur votre portefeuille.

5) Votre portefeuille et les retraits
Vos gains sont ajoutés à votre portefeuille, et vous pouvez en demander le retrait par l'un des moyens annoncés dans votre
marché : virement vers un compte CCP, via BaridiMob avec un RIP, vers un compte bancaire avec un RIB, ou en espèces dans une
agence TAXO après vérification de votre identité. La demande est approuvée par l'équipe financière, et le montant n'est
déduit de votre solde qu'au moment du versement. La destination du retrait est inscrite avec la demande et ne peut plus être
modifiée ensuite ; un virement vers un compte qui n'est pas à votre nom est refusé. Aucune demande n'est versée tant qu'une
somme due n'a pas été réglée.

6) Cartes TAXO
Vous pouvez recharger votre portefeuille avec le code d'une carte TAXO, comme le passager, une seule fois par code.

7) Les avances
Une avance peut vous être proposée dans une limite annoncée ; elle est prélevée automatiquement sur les gains de vos courses.
Si son délai expire sans remboursement, les courses ne vous parviennent plus jusqu'à son remboursement.

8) Annulation et comportement
L'annulation d'une course que vous avez acceptée vous est comptée, et peut donner lieu à des frais au profit du passager. Le
compte est suspendu en cas de plaintes répétées ou d'infraction à la loi, et vos obligations financières demeurent après la
suspension.

9) Fin de la relation
Vous pouvez demander la désactivation de votre compte ; la demande est examinée après le règlement de vos dettes, et
l'historique de vos courses ainsi que le registre de votre portefeuille sont conservés.

10) Modification des conditions
La nouvelle version est publiée dans l'application, et son acceptation est demandée si la modification est substantielle.
"""

#: (نوعُ الوثيقة، التطبيق، المسوّدةُ العربيّة، الفرنسيّ)
DOCUMENTS = (
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.RIDER, seed_policies.DZ_RIDER_PRIVACY, FR_RIDER_PRIVACY),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.RIDER, seed_policies.DZ_RIDER_TERMS, FR_RIDER_TERMS),
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.DRIVER, seed_policies.DZ_DRIVER_PRIVACY, FR_DRIVER_PRIVACY),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.DRIVER, seed_policies.DZ_DRIVER_TERMS, FR_DRIVER_TERMS),
)

#: **ملاحظاتُ المحامي التي كانت في المسوّدات** — تُسلَّم للمالك ولا تُنشر
LEGAL_NOTES = sorted({note for _, _, draft, _ in DOCUMENTS for note in legal_notes(draft)})


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    lines: list[str] = []
    async with session_factory() as session:
        for doc_type, app, draft, french in DOCUMENTS:
            body_ar, body_fr = publishable(draft), french.strip() + "\n"
            live = await policies_service.published(session, country=COUNTRY, doc_type=doc_type, app=app)
            if live is not None and live.body_ar == body_ar and (live.body_fr or "") == body_fr:
                lines.append(f"{doc_type.value}/{app.value}: منشورةٌ بهذا النصّ — لا يُمسّ (v{live.version})")
                continue
            policy = await policies_service.create_version(
                session, country=COUNTRY, doc_type=doc_type, app=app, body_ar=body_ar, body_en=None, body_fr=body_fr,
                requires_reconsent=False,
            )
            previous = await policies_service.publish(session, policy, actor=None)
            await audit.record(
                session, actor=None, action=AuditAction.ACTIVATE, entity_type="privacy_policy", entity_id=policy.id,
                details={"country_code": COUNTRY.value, "doc_type": doc_type.value, "app": app.value,
                         "version": policy.version, "replaced": previous.version if previous else None,
                         "languages": ["ar", "fr"], "reason": REASON},
            )
            lines.append(f"{doc_type.value}/{app.value}: v{policy.version} تُنشر — عربيّ {len(body_ar)} حرفاً · فرنسيّ {len(body_fr)}")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="نشرُ سياسات الجزائر (SPEC §٧٤-ل/١)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for line in asyncio.run(main_async(write=args.apply)):
        print(f"  {line}")
    print(f"  ملاحظاتُ المحامي التي نُزعت من النصّ المنشور ({len(LEGAL_NOTES)}) — تُسلَّم للمالك:")
    for note in LEGAL_NOTES:
        print(f"    · {note}")
    print("✓ نُشرت" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
