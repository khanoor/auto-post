# Instagram Auto-Post — Setup Guide

Ye bot **GitHub Actions** (free, cloud) pe chalta hai — aapka Mac band rahe tab bhi reels apne aap post hongi.
Instagram ki **official Graph API** use hoti hai, isliye password kabhi kahin nahi daalna.

> ⚠️ **Token / password kabhi chat mein, WhatsApp pe, ya kisi file mein mat daalna.** Sirf GitHub Secrets mein (Step 6).

**Kul samay:** ~40 minute (sirf ek baar)

---

## Step 1 — Instagram ko Professional account banao
1. Instagram app → **Profile → ☰ Menu → Settings and privacy → Account type and tools**
2. **Switch to professional account** → **Creator** (ya Business) choose karo.

## Step 2 — Instagram ko Facebook Page se jodo
1. Agar Facebook Page nahi hai: facebook.com → **Pages → Create new Page** (naam: नन्हे किस्से).
2. Page → **Settings → Linked accounts → Instagram → Connect** → apna Instagram account jodo.

## Step 3 — Meta Developer App banao
1. **developers.facebook.com** kholo → apne Facebook account se login → (pehli baar ho to "Get Started" karke developer account banao).
2. **My Apps → Create App**
   - App name: `Nanhe Kisse Poster`
   - Use case: **Other** → App type: **Business** → **Create app**
3. App dashboard mein **Add product** → **Instagram** → **Set up** → **API setup with Facebook login** choose karo.

> App "Development mode" mein hi rehne do. Apne khud ke account pe post karne ke liye App Review ki zaroorat nahi.

## Step 4 — Access Token banao
1. **developers.facebook.com/tools/explorer** (Graph API Explorer) kholo.
2. Right side mein:
   - **Meta App:** `Nanhe Kisse Poster`
   - **User or Page:** *Get User Access Token*
   - **Permissions** mein ye 5 jodo:
     `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`
3. **Generate Access Token** → popup mein apna **Page** aur **Instagram account** select karo → Continue.

## Step 5 — Token ko "kabhi expire na hone wala" banao
1. **developers.facebook.com/tools/debug/accesstoken** kholo → Step 4 wala token paste karo → **Debug**.
2. Neeche **Extend Access Token** button dabao → naya (long-lived) token copy karo.
3. Wapas **Graph API Explorer** mein, upar token box mein ye naya token paste karo, aur query box mein likho:
   ```
   me/accounts?fields=name,access_token,instagram_business_account
   ```
   **Submit** dabao.
4. Result mein apne Page ke saamne do cheezein milengi — dono kahin safe note kar lo (sirf apne paas):
   - `access_token` → ye **Page token** hai → yahi `IG_ACCESS_TOKEN` banega
   - `instagram_business_account` → `id` → yahi `IG_USER_ID` banega (17 se shuru hone wala lamba number)
5. (Check) Is Page token ko phir se Access Token Debugger mein daalo → **Expires: Never** dikhna chahiye. ✅

## Step 6 — GitHub pe repo banao aur Secrets daalo
1. **github.com** pe account banao (agar nahi hai).
2. **New repository** → naam `insta-autopost` → **Private** ✅ → Create.
3. Is folder (`insta-autopost`) ko us repo mein push karo — Terminal mein (repo ka URL GitHub page pe milega):
   ```bash
   cd /Users/noor/projects/reel/insta-autopost
   git remote add origin https://github.com/<aapka-username>/insta-autopost.git
   git push -u origin main
   ```
   (Chaaho to ye step main kar dunga — bas bolo.)
4. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `IG_ACCESS_TOKEN` → Value: Step 5 wala Page token
   - Name: `IG_USER_ID` → Value: Step 5 wala Instagram id

## Step 7 — Test karo (kuch post nahi hoga)
1. Repo → **Actions** tab → (pehli baar) **"I understand my workflows, enable them"**.
2. Left mein **Instagram Auto Post** → **Run workflow** → mode: **check** → Run.
3. 1 minute baad run kholo → **Token check** step mein dikhna chahiye:
   `OK: token sahi hai. Instagram account: @aapka_username`

✅ Ho gaya! Ab bot schedule ke hisaab se apne aap post karega.

---

## Schedule kaise kaam karta hai
| Din | Reel 1 | Reel 2 |
|---|---|---|
| Somvar–Shukravar | 1:00 PM | 7:30 PM |
| Shanivar–Ravivar | 10:00 AM | 7:00 PM |

- Bot `autopost/queue.txt` ki list mein se **agli reel** uthata hai — har slot pe ek.
- **Start date:** `autopost/config.json` mein `"start_date": "2026-11-21"` — isse pehle kuch post nahi hoga. Badalna ho to yahi date badlo.
- **Day 1–2 pehle hi post kar di?** To unke naam `config.json` ke `"skip"` mein daal do, jaise:
  ```json
  "skip": ["day01_17nov_tue/reel1_intro_golu_ki_duniya", "day01_17nov_tue/reel2_golu_aur_toota_gamla"]
  ```
- Koi slot miss ho jaye (GitHub late ho / error) to bot 2 ghante tak koshish karta hai, phir agle slot pe agli reel — **purani reels ek saath kabhi nahi daalta**.
- Kya post hua — `autopost/posted.json` mein link ke saath record hota hai.
- Fail hone par GitHub aapko **email** karega.

## Kabhi bhi turant ek reel post karni ho
Actions → Instagram Auto Post → Run workflow → mode: **post-next-now**

## Nayi reels jodna (Day 16+)
1. Reel folder (`reel.mp4` + `caption.txt`) ko `reels/` mein daalo.
2. Uska naam `autopost/queue.txt` ke end mein jodo.
3. Push karo — bas.

## Dhyan rakho
- Facebook/Instagram ka **password badla** to token band ho jayega → Step 4–6 dobara karke sirf `IG_ACCESS_TOKEN` secret update karo.
- Instagram API se din mein max ~50 posts ho sakte hain — hum 2 karte hain, koi dikkat nahi.
- Meta ka page design kabhi-kabhi badalta hai — koi button na mile to screenshot bhejo, main bata dunga.
- Schedule time badalna ho to `config.json` ke `slots` ke saath `.github/workflows/autopost.yml` ka `cron` bhi badalna padega — mujhe bolo, main kar dunga.
