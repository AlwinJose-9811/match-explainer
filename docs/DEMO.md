# Demo script, viva preparation and backup plan

## Before you present (10 minutes)
- [ ] `python tasks.py serve`, open http://localhost:8000 in Chrome or Edge. Keep it open on the Summary page.
- [ ] Turn Wi-Fi off and click through every page once (the site makes no external requests).
- [ ] Check sound for the Listen button (Edge has the best built-in voices). If there is no voice, skip it.
- [ ] Have the backup video and the PDF printouts of the pages on a phone or USB stick, outside this folder.
- [ ] Rehearse twice with a stopwatch. Target 5 minutes.

## 5-minute demo (the final, Argentina 3-3 France)
| Time | Do | Say |
|---|---|---|
| 0:00 | Summary page | "Commentary tells you what happened. This tells you why, in plain words. This is the 2022 World Cup final." |
| 0:30 | Hover **xG (our model)** and **Possession** | "Every term explains itself. xG is the quality of a chance: 0.30 means about 3 in 10 shots like it score." Press **Listen to the story**. |
| 1:15 | Pitch page, drag the slider | "Each dot is a player's average position. These dashed lines show how high each team defended. Around minute 60 Argentina sat deep and France pushed up." |
| 2:15 | Key moments, open **35:22 Di Maria goal**, press Play | "The data rebuilds the move. Eight steps from Molina to Di Maria. The explanation says why it worked: a quick counter." |
| 3:00 | Press **Play** again and watch the French defenders, then switch on **Last defender line** and click **Freeze at the key pass** | "The bold line is the ball. Every other dot is a player on camera, with the French defenders as squares and their runs as thin trails. The key pass slips behind the last visible defender." Say once: "player paths between camera snapshots are estimates; the data has no full tracking." |
| 3:30 | Open **80:59 Mbappe goal** (and, if there is time, the **59:51 Messi chance**), then point at the penalty cards | "Three of the six goals were penalties. They have no build-up, so they are shown as simple cards." |
| 4:00 | Model card | "Trained on 22 thousand shots from 877 league matches, tested on Euro 2020. Beats the distance-and-angle baseline, sits behind StatsBomb's own xG, and the limits are listed." |
| 4:40 | Show the repository README | "Everything rebuilds with `python tasks.py all`, and the same pitch and replay code could later show positions detected from video." |

If something fails: refresh the page; if the server is down, restart `python tasks.py serve`; if the laptop fails, play the backup video.

## Likely questions
| Question | Answer |
|---|---|
| What is the machine learning? | A supervised xG classifier: logistic regression on pre-shot features, tuned with 5-fold cross-validation grouped by match, tested on a held-out competition with log loss, Brier, AUC and a calibration plot. |
| How did you avoid leakage? | Only information known at the moment of the shot is used. A test fails the build if an outcome, end location or StatsBomb xG feature appears. The split is by competition, never by random shot, because shots in a match are correlated. |
| Why not use StatsBomb's xG? | It is shown as a benchmark. Training our own demonstrates the method; the gap (log loss 0.264 against 0.251) is reported honestly. |
| Why not predict who wins? | Match outcomes are noisy and not explanatory. xG explains chance quality, which is what the site teaches. |
| How accurate are the tactics labels? | They are rule-based on average positions from event data, so they are approximate; thresholds come from the five matches and the page says so. |
| Is the text reliable? | It is built from templates and facts only, checked by a validator that rejects any name or number not in the facts, and always labelled Automated analysis. No language model is used. |
| What would you do next? | More matches, a language model with the same validator for richer wording, then a computer-vision pipeline for video using the same pitch and replay components. |
| Is it legal to use the data? | Free with attribution under StatsBomb's user agreement; add their logo before publishing publicly. No broadcast footage is used. |
| What are the limits? | Event data has no tracking; 360 shows visible players only; five matches; one fixed chance for penalties. |

## Backup recording (3 minutes)
1. Press Win+G (Xbox Game Bar), click Capture, then Record, or use OBS.
2. Follow the table above with the site open. Speak slowly and keep to 3 minutes.
3. Save the video to a phone or USB stick, outside the repository.
4. Print each page to PDF as a second backup: in Chrome press Ctrl+P, choose Save as PDF, and do this for Summary, Pitch, Key moments, Shots & xG and Model card.

## Still for you to do (the project cannot do these)
- [ ] Test the site with three people who do not follow football: can each explain one moment after watching it? (success criterion S6)
- [ ] Confirm with your teacher whether a trained model and this submission format are what is required.
- [ ] Read StatsBomb's LICENSE and add their logo before making the repository or site public.
