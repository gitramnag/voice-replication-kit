# Complete voice capture script

156 prompts across three tiers. The estimated recorded audio is 35.9 minutes.

Use the exact item IDs as filenames or ledger keys. Keep recordings private.

## Block A: Calibration

### `A-01`: Calibration

Tier 1. Style: `calibration`. Target: 12 seconds.

Direction: SILENCE. Do not speak, do not move, do not touch the desk. This measures the room noise floor, which sets the quality ceiling for everything after it.

> [record 12 seconds of complete silence]

### `A-02`: Calibration

Tier 1. Style: `calibration`. Target: 13 seconds.

Direction: Normal speaking volume, the level you would actually narrate at. Peak level and SNR are checked before you commit to the real script.

> This is a level check at my normal narration volume. One, two, three, four, five. The quick brown fox jumps over the lazy dog. I am speaking exactly as I would for a real demo recording.

### `A-03`: Calibration

Tier 1. Style: `calibration`. Target: 9 seconds.

Direction: Now your LOUDEST likely moment, so headroom can be confirmed and nothing clips later in Block B.

> And here is the best part! Look at that! Fourteen thousand rows, instantly!

## Block B: Emotion reference

### `B-neutral-1`: Emotion reference

Tier 1. Style: `narration_neutral`. Target: 16 seconds.

Direction: One continuous take. Do not let the energy fall on the last sentence.

> The dashboard pulls live data from three separate sources and reconciles them every fifteen seconds. On the left you can see the current queue depth. On the right, the same figures broken out by region, so you can tell at a glance where the backlog is forming.

Source: original

### `B-neutral-2`: Emotion reference

Tier 1. Style: `narration_neutral`. Target: 15 seconds.

Direction: Steady, procedural. Slight downward inflection on each full stop.

> Setting this up takes two steps. First, you connect your data source, and the system reads the schema automatically. Second, you pick the fields you actually care about. Everything else stays hidden until you need it, which keeps the default view readable.

Source: original

### `B-neutral-3`: Emotion reference

Tier 2. Style: `narration_neutral`. Target: 15 seconds.

Direction: Same voice as the previous two. Consistency across the three takes is what makes this style reliable.

> Underneath, each request is logged with a timestamp, the user who made it, and the result. That history is what makes the audit trail possible. You can filter it by date, export it as a spreadsheet, or hand it straight to your compliance team.

Source: original

### `B-warm-1`: Emotion reference

Tier 1. Style: `warm_friendly`. Target: 15 seconds.

Direction: Actually smile. Keep the smile all the way to the final word.

> Hey, thanks for stopping by. I want to walk you through something we have been building for a few months now, and honestly, I am quite proud of how it turned out. It is going to take about four minutes, so grab a coffee and settle in.

Source: original

### `B-warm-2`: Emotion reference

Tier 1. Style: `warm_friendly`. Target: 15 seconds.

Direction: A sign-off. Warm, relaxed, slightly slower than neutral.

> So that is the whole tour. I hope it gave you a decent feel for how it works day to day. If anything looked interesting, or if you just want to poke around yourself, the link is right below this video. Thanks for watching.

Source: original

### `B-warm-3`: Emotion reference

Tier 2. Style: `warm_friendly`. Target: 14 seconds.

Direction: Inclusive and welcoming.

> Before we dive in, a quick word about who this is for. If you have ever had to pull a report together on a Friday evening, you are exactly the person we built this for. Welcome, you are in good company.

Source: original

### `B-excited-1`: Emotion reference

Tier 1. Style: `excited_energetic`. Target: 15 seconds.

Direction: Bright and fast, but keep articulation crisp. Excitement, not volume.

> Okay, this is the part I have been waiting to show you. Watch what happens when I hit refresh. That entire report, every chart, every number, rebuilt in under two seconds. The first time I saw that, I actually laughed out loud.

Source: original

### `B-excited-2`: Emotion reference

Tier 1. Style: `excited_energetic`. Target: 14 seconds.

Direction: Building energy across the sentences. Do not plateau early.

> And here is the best bit. You do not have to configure any of it. It just works, straight out of the box, on day one. No setup call, no onboarding form, no waiting around for someone to provision your account.

Source: original

### `B-excited-3`: Emotion reference

Tier 2. Style: `excited_energetic`. Target: 15 seconds.

Direction: Hit the standalone exclamation properly. That single word carries the style.

> Look at that. Fourteen thousand rows, sorted, filtered, and grouped, instantly. This used to take our analysts an entire afternoon. An afternoon! Now it happens faster than you can finish reading the question. That is the whole point of this thing.

Source: original

### `B-serious-1`: Emotion reference

Tier 1. Style: `serious_authoritative`. Target: 17 seconds.

Direction: Drop your pitch. Slow down. Let the last sentence land hard and cold.

> Let us be clear about the stakes. A single misconfigured permission can expose customer records to the entire organisation. It has happened to companies far larger than ours, and it will happen again. This is not a theoretical risk. It is a Tuesday afternoon.

Source: original

### `B-serious-2`: Emotion reference

Tier 1. Style: `serious_authoritative`. Target: 17 seconds.

Direction: Measured and factual. Authority through calm, not force.

> Every credential is encrypted at rest and in transit. Nothing is written to disk in plain text. Access is logged, reviewed monthly, and revoked the moment someone changes role. These are not optional extras. They are the minimum bar for handling data like this.

Source: original

### `B-serious-3`: Emotion reference

Tier 2. Style: `serious_authoritative`. Target: 16 seconds.

Direction: Grave and direct. Slight weight on the repeated word at the end.

> The current process has three failure points, and we have hit all three in the past year. Each time, the cost was measured in days of lost work. We cannot keep absorbing that. Something has to change, and it has to change now.

Source: original

### `B-curious-1`: Emotion reference

Tier 1. Style: `curious_questioning`. Target: 15 seconds.

Direction: Let the two questions genuinely rise, then answer yourself thoughtfully.

> So what actually happens when two people edit the same record at once? Does one of them silently lose their work? Or does the system notice, stop, and ask? That question sounds small, but it decides whether anyone trusts the tool.

Source: original

### `B-curious-2`: Emotion reference

Tier 1. Style: `curious_questioning`. Target: 15 seconds.

Direction: The numbered guesses should sound like real guesses, each with its own rise.

> Why does this matter? Well, think about how you work now. How many browser tabs do you have open just to answer one question? Three? Five? And how many of them are showing numbers that disagree with each other?

Source: original

### `B-curious-3`: Emotion reference

Tier 2. Style: `curious_questioning`. Target: 15 seconds.

Direction: Open on a real question, then narrow into the answer.

> But is it fast enough to use in a live meeting? That was the real test. Not fast in a benchmark, not fast on a developer's laptop, but fast while eleven people are watching and waiting for an answer.

Source: original

### `B-empathetic-1`: Emotion reference

Tier 1. Style: `empathetic_calm`. Target: 17 seconds.

Direction: Soft and slow. Quieter than neutral, but keep it voiced. Do not go breathy.

> I know this part is frustrating. You have done everything right, the file is correct, and it still will not upload. We have all been there, staring at a progress bar at half past six. So let me show you what is actually going wrong, and how to fix it.

Source: original

### `B-empathetic-2`: Emotion reference

Tier 1. Style: `empathetic_calm`. Target: 15 seconds.

Direction: Reassuring and patient. Imagine talking to a nervous new colleague.

> It is completely normal to feel a bit lost the first week. There is a lot here, and nobody expects you to hold it all in your head. Take it slowly. You only need three of these screens to do your job well.

Source: original

### `B-empathetic-3`: Emotion reference

Tier 2. Style: `empathetic_calm`. Target: 16 seconds.

Direction: A genuine apology, then gentle resolve. Sincere, not performed.

> If you have lost work this way before, I am sorry. It is a genuinely awful feeling, and it was not your fault. The old system made it far too easy to do. That is precisely why we changed it. You should not have to be careful for the software's sake.

Source: original

### `B-punchy-1`: Emotion reference

Tier 1. Style: `emphatic_punchy`. Target: 16 seconds.

Direction: Real silence between the short sentences, roughly half a second each. Do not rush them together.

> One dashboard. One number. One source of truth. No spreadsheets. No arguing about whose figures are right. You open it, you look, you know. That is it. That is the whole pitch.

Source: original

### `B-punchy-2`: Emotion reference

Tier 1. Style: `emphatic_punchy`. Target: 15 seconds.

Direction: Three isolated words to open. Stress each equally, with a beat between.

> Faster. Simpler. Cheaper. Pick all three, because for once you actually can. Ninety seconds to set up. Zero training required. And it costs less than the tool you are already unhappy with.

Source: original

### `B-punchy-3`: Emotion reference

Tier 2. Style: `emphatic_punchy`. Target: 14 seconds.

Direction: Imperative and direct. The final one-word sentence needs a full beat before it.

> Stop guessing. Start measuring. The data is already there, sitting in your systems, waiting. All you have to do is look at it. So look at it. Today.

Source: original

### `B-awe-1`: Emotion reference

Tier 2. Style: `awe_wonder`. Target: 18 seconds.

Direction: Slower than feels natural. Let the vowels open and sustain. You are seeing something you cannot quite believe.

> And then the mist drew back, and he saw it at last. Towers of white stone rising sheer from the valley floor, catching the first light, higher than any work of mortal hands. Seven walls, seven gates, and above them all a banner he had only ever heard named in songs.

Source: original

### `B-awe-2`: Emotion reference

Tier 2. Style: `awe_wonder`. Target: 18 seconds.

Direction: Hushed reverence rather than volume. The last clause should feel like a discovery.

> The doors were older than the kingdom. Carved into them were the names of every soul who had passed through, and there were more names than there are stars a man can count on a clear night. She set her palm against the wood, and felt it answer her, warm as a living thing.

Source: original

### `B-awe-3`: Emotion reference

Tier 3. Style: `awe_wonder`. Target: 15 seconds.

Direction: Let the silence after the third sentence do the work before you finish.

> Below them the whole world opened. Rivers like threads of silver, forests dark as spilled ink, and beyond it all the sea, burning gold from edge to edge. Nobody spoke. There was nothing to say that would not have made it smaller.

Source: original

### `B-sorrow-1`: Emotion reference

Tier 2. Style: `sorrow_grief`. Target: 17 seconds.

Direction: Restrained. Let the breath run a little short at the ends of phrases. Do not perform crying.

> They buried him at dusk, under the ash tree he had planted as a boy. There was no speech, because nobody could manage one. His sister put her hand on the stone and left it there a long while, and when she finally walked away, she did not look back.

Source: original

### `B-sorrow-2`: Emotion reference

Tier 2. Style: `sorrow_grief`. Target: 16 seconds.

Direction: Quiet and inward, as if talking mostly to yourself.

> I keep finding his things. A glove in the pocket of my coat. A book with the page still turned down where he stopped reading. Every one of them is a small door I cannot help opening, and behind every one of them, he is still alive.

Source: original

### `B-sorrow-3`: Emotion reference

Tier 3. Style: `sorrow_grief`. Target: 17 seconds.

Direction: Flat and tired for most of it, then a small break of feeling on the last two words.

> She was the last of them. She had outlived her brothers, her husband, and both of her children, and when the letters stopped coming there was no one left who remembered her name as a girl. That is the part nobody warns you about. Not the dying. The forgetting.

Source: original

### `B-anger-1`: Emotion reference

Tier 2. Style: `anger_fierce`. Target: 17 seconds.

Direction: Clenched, not shouted. Watch the level meter: pushed volume will clip and clipping ruins the clip permanently.

> No. You do not get to say that to me. Not after everything I gave to this, not after the years I spent holding it together while you looked the other way. You will sit down, and you will listen, and for once in your life you will hear it.

Source: original

### `B-anger-2`: Emotion reference

Tier 2. Style: `anger_fierce`. Target: 16 seconds.

Direction: Open on a hard stop, then hold the fury level rather than escalating into a shout.

> Enough! I have heard enough. You came into my house, you ate at my table, and you lied to my face about the one thing that mattered. Get out. Take your horse and your gold and your excuses, and do not come back while I am still breathing.

Source: original

### `B-anger-3`: Emotion reference

Tier 3. Style: `anger_fierce`. Target: 16 seconds.

Direction: Cold anger rather than hot. Quieter, and more frightening for it.

> They burned the village. Not the soldiers, not the enemy, but our own men, on our own orders, because someone in a warm room decided it was simpler. I will carry that. But I will not forgive it, and I will not pretend it was necessary.

Source: original

### `B-tender-1`: Emotion reference

Tier 2. Style: `tender_intimate`. Target: 16 seconds.

Direction: Very close and soft, but stay voiced. Slow the whole thing down by about a quarter.

> Hey. You are alright. I have got you. Just breathe with me, in and out, that is it. Nothing has to be decided tonight, and nobody is angry with you, and you are not in trouble. Whatever it is, we will look at it together in the morning.

Source: original

### `B-tender-2`: Emotion reference

Tier 2. Style: `tender_intimate`. Target: 16 seconds.

Direction: Fond and amused and a little wistful, all at once.

> You were so small. I could hold all of you in my two hands, and I was terrified I would do it wrong. And now look at you. Taller than me, arguing with me, wonderfully certain about everything. I would not change a single day of it.

Source: original

### `B-tender-3`: Emotion reference

Tier 3. Style: `tender_intimate`. Target: 14 seconds.

Direction: Almost nothing in the voice. Warm, low, unhurried, content.

> Stay a minute longer. The fire is still good and the roads will keep. I like the quiet with you in it. That is all. There is nothing I need to say, I would just rather you were here than not.

Source: original

### `B-suspense-1`: Emotion reference

Tier 2. Style: `suspense_hushed`. Target: 16 seconds.

Direction: Voiced whisper, urgent, short breaths. Keep the vocal folds engaged so every word remains clearly voiced.

> Do not move. Listen. There it is again, under the floor, the same three taps, and it has been an hour since anyone else was in this house. I locked the door myself. I checked it twice. Whatever is down there, it knows we are standing here.

Source: original

### `B-suspense-2`: Emotion reference

Tier 2. Style: `suspense_hushed`. Target: 17 seconds.

Direction: Tight and fast and low. Instructions given under real pressure.

> Keep your voice down and keep walking. Do not look at the man by the fountain and do not slow down when we pass him. If we reach the bridge before the bell rings we will be fine. If we do not, then you run, and you do not stop for me.

Source: original

### `B-suspense-3`: Emotion reference

Tier 3. Style: `suspense_hushed`. Target: 14 seconds.

Direction: Dread rather than fear. Slow, deliberate, and quiet right to the final word.

> The lamp went out on its own. There was no draught, the window was shut, and the wick was hardly touched. And in the dark, for just a moment, I heard something breathing that was not either of us.

Source: original

### `B-playful-1`: Emotion reference

Tier 2. Style: `playful_wry`. Target: 16 seconds.

Direction: Dry and arch. Underplay it. The timing carries the joke, not the volume.

> Oh, marvellous. Another meeting about the meeting. I shall bring a cushion and my will. Honestly, at this point I have spent more of my life in that room than in my own house, and the room has better coffee, which is the truly insulting part.

Source: original

### `B-playful-2`: Emotion reference

Tier 2. Style: `playful_wry`. Target: 16 seconds.

Direction: Deadpan the whole way, and leave a real beat before the last sentence.

> He assured me, with a completely straight face, that he had read the whole document. All ninety pages. In eleven minutes. Between two other calls. I said nothing. I simply asked him what he thought of appendix four. There is no appendix four.

Source: original

### `B-playful-3`: Emotion reference

Tier 3. Style: `playful_wry`. Target: 15 seconds.

Direction: Mock-formal innocence. Enjoy it, but do not wink at the audience.

> I am not saying I told you so. I would never say that. I am simply noting, for the historical record, that a certain person predicted this exact outcome in March, in writing, and was described at the time as being unhelpfully negative.

Source: original

### `B-triumph-1`: Emotion reference

Tier 2. Style: `triumphant_declaratory`. Target: 17 seconds.

Direction: Chest-forward and ringing. Proclaiming to a room. Full breath, strong finals.

> It held. The wall held, the gate held, and when the sun came up there were still men standing on it. Sound the bells. Every one of them, all the way to the coast, until the last village knows. Tonight we are still here, and tomorrow we are still here.

Source: original

### `B-triumph-2`: Emotion reference

Tier 2. Style: `triumphant_declaratory`. Target: 16 seconds.

Direction: Formal proclamation. Slower and grander than feels comfortable.

> Then let it be written, and let it be read aloud in every hall from the mountains to the sea. The debt is paid. The exile is ended. From this day forward no one bearing that name shall be turned from any door in this kingdom.

Source: original

### `B-triumph-3`: Emotion reference

Tier 3. Style: `triumphant_declaratory`. Target: 16 seconds.

Direction: Modern and warm rather than grand. Exhausted, delighted triumph.

> We did it. Eleven months, four false starts, and one very long weekend, and it is done, and it works. Look at the board. Every single light is green. Go home. Sleep. And then come back, because I have got an idea about the next one.

Source: original

## Block C: Phonetic coverage

### `C-01`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Read these plainly and consistently. They exist for phoneme coverage, not performance. Do not add emotion.

> The birch canoe slid on the smooth planks.

Source: public domain: Harvard sentences, IEEE 1969

### `C-02`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Glue the sheet to the dark blue background.

### `C-03`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> It is easy to tell the depth of a well.

### `C-04`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> These days a chicken leg is a rare dish.

### `C-05`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Rice is often served in round bowls.

### `C-06`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The juice of lemons makes fine punch.

### `C-07`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The box was thrown beside the parked truck.

### `C-08`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The hogs were fed chopped corn and garbage.

### `C-09`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Four hours of steady work faced us.

### `C-10`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> A large size in stockings is hard to sell.

### `C-11`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The boy was there when the sun rose.

### `C-12`: Phonetic coverage

Tier 1. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> A rod is used to catch pink salmon.

### `C-13`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 5 seconds.

Direction: Plain and even.

> The source of the huge river is the clear spring.

### `C-14`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Kick the ball straight and follow through.

### `C-15`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Help the woman get back to her feet.

### `C-16`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> A pot of tea helps to pass the evening.

### `C-17`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> Smoky fires lack flame and heat.

### `C-18`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The soft cushion broke the man's fall.

### `C-19`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The salt breeze came across from the sea.

### `C-20`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The girl at the booth sold fifty bonds.

### `C-21`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The small pup gnawed a hole in the sock.

### `C-22`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The fish twisted and turned on the bent hook.

### `C-23`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 5 seconds.

Direction: Plain and even.

> Press the pants and sew a button on the vest.

### `C-24`: Phonetic coverage

Tier 2. Style: `narration_neutral`. Target: 4 seconds.

Direction: Plain and even.

> The swan dive was far short of perfect.

## Block D: Technical vocabulary

### `D-01`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Say the acronyms the way you naturally would in a real demo. Keep the pronunciation steady across repeated takes.

> The API returns JSON, and every endpoint is documented in the OpenAPI schema.

### `D-02`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural demo delivery.

> We authenticate with OAuth two point oh, and single sign-on is handled through Azure Active Directory.

### `D-03`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> The query hits PostgreSQL directly, so there is no caching layer to invalidate.

### `D-04`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> Export it as a CSV, or pull it straight from the SDK if you would rather script it.

### `D-05`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural demo delivery.

> Our CI CD pipeline runs on GitHub Actions, and the whole suite finishes in about four minutes.

### `D-06`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> P ninety-five latency sits at about eighty milliseconds, even under load.

### `D-07`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> The CLI is a single binary. No npm, no Docker, no runtime to install.

### `D-08`: Technical vocabulary

Tier 1. Style: `narration_neutral`. Target: 5 seconds.

Direction: Natural demo delivery.

> Role-based access control is enforced server-side, not in the UI.

### `D-09`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> Webhooks fire asynchronously, so a slow consumer never blocks the main request.

### `D-10`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> It runs on Kubernetes in production, but locally it is just one process.

### `D-11`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 5 seconds.

Direction: Natural demo delivery.

> The LLM call is cached, which keeps GPU cost predictable.

### `D-12`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> Drop the Figma link into Slack and the bot posts a preview automatically.

### `D-13`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> Throughput scales linearly up to about two thousand requests per second.

### `D-14`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 5 seconds.

Direction: Natural demo delivery.

> Every config value can be overridden by an environment variable.

### `D-15`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> The regex is compiled once at startup and reused for every request.

### `D-16`: Technical vocabulary

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural demo delivery.

> Middleware handles auth, rate limiting, and request logging, in that order.

## Block E: Numbers and units

### `E-01`: Numbers and units

Tier 1. Style: `narration_neutral`. Target: 7 seconds.

Direction: Read the numbers exactly as written, at a natural demo pace. Keep each value clear without over-emphasising it.

> Revenue grew from one point two million to three point eight million in eighteen months.

### `E-02`: Numbers and units

Tier 1. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural pace.

> The file is two hundred and forty megabytes, which compresses down to nineteen.

### `E-03`: Numbers and units

Tier 1. Style: `narration_neutral`. Target: 5 seconds.

Direction: Natural pace.

> Uptime last quarter was ninety-nine point nine seven percent.

### `E-04`: Numbers and units

Tier 1. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural pace.

> We shipped on the third of March, twenty twenty-six, two days ahead of schedule.

### `E-05`: Numbers and units

Tier 1. Style: `narration_neutral`. Target: 5 seconds.

Direction: Natural pace.

> It costs twelve dollars per seat per month, billed annually.

### `E-06`: Numbers and units

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural pace.

> Response times dropped from four point six seconds to three hundred milliseconds.

### `E-07`: Numbers and units

Tier 2. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural pace.

> Out of fourteen thousand two hundred records, exactly seven failed validation.

### `E-08`: Numbers and units

Tier 2. Style: `narration_neutral`. Target: 6 seconds.

Direction: Natural pace.

> The meeting is at half past nine on Thursday, in room four B.

### `E-09`: Numbers and units

Tier 2. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural pace.

> That is a forty-two percent reduction, or roughly eleven hours a week per analyst.

### `E-10`: Numbers and units

Tier 2. Style: `narration_neutral`. Target: 7 seconds.

Direction: Natural pace.

> Version two point one point four is out now, and two point two lands in Q three.

## Block F: Prosody drills

### `F-01`: Prosody drills

Tier 2. Style: `mixed`. Target: 4 seconds.

Direction: Two real questions. Let both rise.

> Did you save it? Or did you just close the tab?

### `F-02`: Prosody drills

Tier 2. Style: `mixed`. Target: 7 seconds.

Direction: A list. Keep each item level, then fall on the last one.

> You can filter by date, by owner, by status, by region, or by any combination of the four.

### `F-03`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Contrast. Stress the corrections hard.

> It is not slower. It is faster. Considerably faster.

### `F-04`: Prosody drills

Tier 2. Style: `mixed`. Target: 4 seconds.

Direction: Interrupt yourself. Surprised, a little sharp.

> Wait. Go back. That number cannot be right.

### `F-05`: Prosody drills

Tier 2. Style: `mixed`. Target: 7 seconds.

Direction: Sequence. Build slightly with each step.

> First we ingest, then we validate, then we reconcile, and only then do we publish.

### `F-06`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Mild pleasant surprise on the second sentence.

> I thought it would take a week. It took an afternoon.

### `F-07`: Prosody drills

Tier 2. Style: `mixed`. Target: 3 seconds.

Direction: Brisk and light. A transition line.

> Ready? Here we go.

### `F-08`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Three quick negatives, then a correction. Conversational.

Speech form: single-speaker dialogue turn. Record only the displayed turn.

Dialogue context: A single speaker corrects a selection after the other person points to the wrong item.

> No, no, no. Not that one. The one underneath it.

### `F-09`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Wry, candid, a little self-deprecating.

> Honestly? I did not expect it to work either.

### `F-10`: Prosody drills

Tier 2. Style: `mixed`. Target: 6 seconds.

Direction: A list of three, then single out the last for emphasis.

> Three things matter here. Speed, accuracy, and trust. Especially trust.

### `F-11`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Deadpan. The second sentence is the joke, so do not sell it.

> You could do it manually. You could also walk to work.

### `F-12`: Prosody drills

Tier 2. Style: `mixed`. Target: 5 seconds.

Direction: Thinking aloud. A real filled pause at the start.

> Hmm. That is interesting. Let me try something.

## Block G: Paralinguistics

### `G-01`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 4 seconds.

Direction: A genuine, light laugh. Do not force it. Think of something actually funny. Two or three seconds is plenty.

> [laugh naturally, no words]

### `G-02`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 3 seconds.

Direction: A short warm chuckle, closed-mouth. Softer than the laugh above.

> [chuckle softly, no words]

### `G-03`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 5 seconds.

Direction: Laugh first, then speak through the tail of it. Let the transition settle naturally into the words.

> Ha! I knew that would happen.

### `G-04`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 3 seconds.

Direction: A thoughtful closed-mouth hum, falling in pitch.

> [hum thoughtfully: mmmm]

### `G-05`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 5 seconds.

Direction: Take an audible breath in, then speak. Do not edit the breath out.

> [audible in-breath] Right. Let us begin.

### `G-06`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 5 seconds.

Direction: A small sigh of relief, then the words.

> [sigh of relief] Phew. That is done.

### `G-07`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 4 seconds.

Direction: Agreement sound, then the word. Both warm.

> Mm-hmm. Exactly.

### `G-08`: Paralinguistics

Tier 3. Style: `paralinguistic`. Target: 3 seconds.

Direction: Clear your throat once, naturally, as you would mid-recording.

> [clear throat once]

## Block H: Long-form continuous read

### `H-01`: Long-form continuous read

Tier 1. Style: `narration_neutral`. Target: 68 seconds.

Direction: One take, all the way through. If you stumble, keep going rather than stopping. This block teaches long-range rhythm and breathing, which short clips cannot, and it becomes the finetuning corpus.

> Let me show you what a normal Monday looks like now. You open the dashboard, and the first thing you see is the one number that actually matters. How many orders are stuck. Last Monday it was six. This Monday it is zero, and that is not luck, it is the new validation step catching problems before they reach the queue. If you click through, you get the detail. Who submitted it, what failed, and the exact field that caused it. No more guessing, no more digging through logs at seven in the morning. And here is the part I like most. When something does go wrong, the person who can fix it gets a message immediately, with the record attached. They do not have to come looking for it. In the four weeks since we turned this on, average resolution time has gone from about eleven hours to just under forty minutes. Same team, same volume, same systems underneath. We just stopped losing information between the steps.

Source: original

### `H-02`: Long-form continuous read

Tier 2. Style: `serious_authoritative`. Target: 70 seconds.

Direction: One take. Starts grave, softens in the middle where you say you want to be honest, then resolves steady and factual. Let that arc happen naturally.

> For years, the reconciliation ran overnight, and nobody looked at it until morning. If it failed at two in the morning, you found out at nine, and by then the day was already lost. That happened eleven times last year. Eleven mornings where the first thing somebody did was apologise to a customer for a number that was wrong. I want to be honest. That was not a technology problem. The code worked. The problem was that no human being was told. So we changed the one thing that mattered. Now, if reconciliation fails, three people get woken up, and the system holds the bad figures back instead of publishing them. It sounds almost too simple to matter. But since March, we have had two failures, both caught within four minutes, and neither one reached a customer. Nobody had to apologise for anything. That is the whole improvement. Not smarter code. Just information reaching a person in time to act on it.

Source: original

### `H-03`: Long-form continuous read

Tier 3. Style: `narration_neutral`. Target: 72 seconds.

Direction: One take. Pure instructional walkthrough. Steady, patient, slightly slower than conversational. This is the exact register most demo narration needs.

> Let us walk through setting up your first workspace. Start by clicking New Workspace in the top right corner. Give it a name you will recognise in six months, because you will not remember what Test Two meant. Next, choose a data source. If your source is not listed, pick Generic SQL and paste the connection string. The system will read the schema and show you every table it found, along with a row count, so you can sanity check that you are pointed at production and not at a stale copy. Now select the tables you need. My advice is to start with fewer than you think. You can always add more, and a smaller workspace loads faster. Once you have chosen, click Validate. This takes about twenty seconds, and it checks three things. That the credentials work, that the tables are readable, and that nothing has a column type we cannot map. If all three pass, you are done. Click Create, and your workspace opens automatically.

Source: original

### `H-04`: Long-form continuous read

Tier 3. Style: `awe_wonder`. Target: 75 seconds.

Direction: One take, dramatic register, with a real emotional arc: wonder, then dread, then resolve. Keep the movement natural rather than holding one mood.

> They came over the last ridge a little before dawn, and none of them spoke, because the valley below was not what the maps had promised. Where there should have been forest there was a lake, black and perfectly still, and standing in the middle of it, half sunk and leaning, was a tower of pale stone. It was enormous. It was older than anything any of them had a word for. Birds went around it rather than over it. And then the light came up properly, and they saw that the whole surface of the lake was covered in small boats, hundreds of them, empty, drifting, all facing the tower as though they had been rowed out and abandoned there on purpose. Nobody wanted to be the first to say it. Finally the youngest of them, who had never been further than the market road, put down her pack and said, well. We did come all this way. And she started down the slope, and one by one, so did everyone else.

Source: original

## Block I: Literary classics (public domain)

### `I-01`: Literary classics (public domain)

Tier 2. Style: `serious_authoritative`. Target: 20 seconds.

Direction: Parallel construction, ten clauses. Vary the stress across the pairs rather than chanting them identically; the rhythm is the exercise.

> It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness, it was the epoch of belief, it was the epoch of incredulity, it was the season of Light, it was the season of Darkness, it was the spring of hope, it was the winter of despair.

Source: public domain: Charles Dickens, A Tale of Two Cities, 1859

### `I-02`: Literary classics (public domain)

Tier 2. Style: `suspense_hushed`. Target: 15 seconds.

Direction: Flat and matter-of-fact, which is what makes it eerie. Do not add spookiness; let the words do it.

> Marley was dead, to begin with. There is no doubt whatever about that. The register of his burial was signed by the clergyman, the clerk, the undertaker, and the chief mourner. Old Marley was as dead as a door-nail.

Source: public domain: Charles Dickens, A Christmas Carol, 1843

### `I-03`: Literary classics (public domain)

Tier 2. Style: `sorrow_grief`. Target: 16 seconds.

Direction: Thinking, not declaiming. This is a man working out a problem, and the verse should sound like reasoning rather than recitation.

> To be, or not to be, that is the question: whether 'tis nobler in the mind to suffer the slings and arrows of outrageous fortune, or to take arms against a sea of troubles, and by opposing end them.

Source: public domain: William Shakespeare, Hamlet, c.1600

### `I-04`: Literary classics (public domain)

Tier 2. Style: `sorrow_grief`. Target: 15 seconds.

Direction: Exhausted and hollow, then two hard stresses on the final three words.

> Tomorrow, and tomorrow, and tomorrow, creeps in this petty pace from day to day, to the last syllable of recorded time; and all our yesterdays have lighted fools the way to dusty death. Out, out, brief candle!

Source: public domain: William Shakespeare, Macbeth, c.1606

### `I-05`: Literary classics (public domain)

Tier 3. Style: `suspense_hushed`. Target: 17 seconds.

Direction: Heavy internal rhyme and a strong beat. Lean into the metre rather than fighting it, and keep it quiet.

> Once upon a midnight dreary, while I pondered, weak and weary, over many a quaint and curious volume of forgotten lore, while I nodded, nearly napping, suddenly there came a tapping, as of someone gently rapping, rapping at my chamber door.

Source: public domain: Edgar Allan Poe, The Raven, 1845

### `I-06`: Literary classics (public domain)

Tier 3. Style: `narration_neutral`. Target: 16 seconds.

Direction: Conversational and dry, as though starting a story you have told before.

> Call me Ishmael. Some years ago, never mind how long precisely, having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world.

Source: public domain: Herman Melville, Moby-Dick, 1851

### `I-07`: Literary classics (public domain)

Tier 3. Style: `anger_fierce`. Target: 18 seconds.

Direction: Rising defiance. Starts contained and controlled, ends unmistakably free. Do not shout the last line; let it ring.

> Do you think, because I am poor, obscure, plain, and little, I am soulless and heartless? You think wrong! I have as much soul as you, and full as much heart. I am no bird; and no net ensnares me: I am a free human being with an independent will.

Source: public domain: Charlotte Bronte, Jane Eyre, 1847

### `I-08`: Literary classics (public domain)

Tier 3. Style: `serious_authoritative`. Target: 17 seconds.

Direction: Measured and steady, one condition at a time. Resist building to a climax; the restraint is the point.

> If you can keep your head when all about you are losing theirs and blaming it on you; if you can trust yourself when all men doubt you, but make allowance for their doubting too; if you can wait and not be tired by waiting.

Source: public domain: Rudyard Kipling, If, 1910

## Block J: Plain reading (top-up)

### `J-01`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 24 seconds.

Direction: Start plainly and stay plain the whole way. This is the single most valuable kind of material in the whole top-up.

> I should probably explain how I ended up doing this for a living. It was not a plan. I finished university with a degree I had no intention of using, took a job that was meant to last three months, and stayed for six years. Somewhere in the middle of that I discovered I was quite good at explaining complicated things to people who were in a hurry.

Source: original

### `J-02`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 23 seconds.

Direction: Read this exactly as you would read aloud to a colleague. Use your ordinary pace and tone; do not add a performance.

> Most systems do not fail all at once. They fail slowly, in ways nobody notices, until one ordinary Tuesday the thing that has been quietly broken for months finally matters. The interesting question is never why it broke. It is why nobody saw it, and the answer is almost always that the information existed but never reached a person who could act on it.

Source: original

### `J-03`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 23 seconds.

Direction: Read this exactly as you would read aloud to a colleague. Use your ordinary pace and tone; do not add a performance.

> The office had one window that actually opened, and by unspoken agreement it belonged to whoever arrived first. I was rarely first. What I remember most from that year is not the work but the sound of the building waking up. The lift, the kettle, somebody's terrible radio two floors down, and then the particular silence that arrived about ten minutes before a deadline.

Source: original

### `J-04`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 23 seconds.

Direction: Read this exactly as you would read aloud to a colleague. Use your ordinary pace and tone; do not add a performance.

> There is a useful distinction between a problem and a constraint. A problem is something you can solve, and once solved it stays solved. A constraint is something you design around, and it never goes away. Most of the frustration I see in teams comes from treating a constraint as though it were a problem, and then being surprised when the effort produces nothing durable.

Source: original

### `J-05`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 19 seconds.

Direction: Read this exactly as you would read aloud to a colleague. Use your ordinary pace and tone; do not add a performance.

> People ask me what the hardest part is, and they expect me to say something technical. It is not technical. The hardest part is getting eleven people who all agree in principle to also agree on the specific words in a specific document by a specific Friday. Everything else is comparatively straightforward.

Source: original

### `J-06`: Plain reading (top-up)

Tier 1. Style: `narration_neutral`. Target: 20 seconds.

Direction: Read this exactly as you would read aloud to a colleague. Use your ordinary pace and tone; do not add a performance. This one is deliberately descriptive, for phonetic variety.

> The river ran shallow and brown that summer, and you could walk across it in most places without getting your knees wet. Children fished for things that were not really there. An old bridge, closed for years, still carried a faded sign warning lorries about a weight limit that no longer applied to anything.

Source: original

## Block K: Emotion, natural register (top-up)

### `K-neutral-1`: Emotion, natural register (top-up)

Tier 1. Style: `narration_neutral`. Target: 20 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Explain a screen to someone in a flat, useful tone.

> This next screen is where most people spend their day, so it is worth a minute. Everything on the left is filters, everything in the middle is results, and the panel on the right only appears when you have selected something. If it looks empty the first time you open it, that is expected.

Source: original

### `K-neutral-2`: Emotion, natural register (top-up)

Tier 1. Style: `narration_neutral`. Target: 20 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Deliver the caveat plainly.

> Before we go further, one thing about permissions. What you can see here depends entirely on which team you are in, so if your screen looks different from mine, that is not a bug. I have got the administrator view, which is why I can see everything, including the parts most people should not.

Source: original

### `K-warm-1`: Emotion, natural register (top-up)

Tier 1. Style: `warm_friendly`. Target: 17 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Greet somebody you genuinely like. Smile, but do not slow down or soften deliberately.

Speech form: single-speaker dialogue turn. Record only the displayed turn.

Dialogue context: A single speaker greets a colleague and invites questions.

> Right, good to see you. I have been looking forward to this one, honestly. Grab a seat, and if you have questions just interrupt me, I would much rather do this as a conversation than talk at you for twenty minutes.

Source: original

### `K-warm-2`: Emotion, natural register (top-up)

Tier 1. Style: `warm_friendly`. Target: 17 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Thank a busy person. Stay warm but brisk.

Speech form: single-speaker dialogue turn. Record only the displayed turn.

Dialogue context: A single speaker thanks a busy colleague and sets expectations.

> Thanks for making the time, I know your calendar is not exactly generous at the moment. This should not take long, and if it turns out to be useful I will send you the link afterwards so you can poke around on your own.

Source: original

### `K-excited-1`: Emotion, natural register (top-up)

Tier 1. Style: `excited_energetic`. Target: 17 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Sound genuinely pleased. Talk faster, not louder.

> Okay so this is the bit I actually wanted to show you. Watch the top right corner. Ready? There. That took two seconds. It used to take an afternoon, and I am still slightly annoyed about how long we put up with the old way.

Source: original

### `K-excited-2`: Emotion, natural register (top-up)

Tier 1. Style: `excited_energetic`. Target: 16 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Sound pleasantly surprised and keep it conversational.

> And it works on the phone too, which I genuinely did not expect to be possible when we started. Same data, same filters, no separate app to install. I showed my brother and he thought it was a different product.

Source: original

### `K-serious-1`: Emotion, natural register (top-up)

Tier 1. Style: `serious_authoritative`. Target: 21 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Let the consequence register without forcing a lower or slower voice.

> I want to be careful about how I put this, because it matters. The number on that dashboard is what people will make decisions from, and if it is wrong nobody finds out until the decision has already been made. So the accuracy of that one figure is not a technical detail. It is the whole product.

Source: original

### `K-serious-2`: Emotion, natural register (top-up)

Tier 1. Style: `serious_authoritative`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay level and factual; let calm carry the authority.

> We should talk about what happens when this fails, because it will. Not often, and not catastrophically, but it will. The question I care about is how quickly somebody knows, and whether the person who finds out is the person who can do something about it.

Source: original

### `K-curious-1`: Emotion, natural register (top-up)

Tier 1. Style: `curious_questioning`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Wonder aloud and let each question arrive naturally.

> So what happens if two people are in here at the same time? Does it warn them? Does it just take whoever saved last? I asked that in the first week and got three different answers, which told me something about how well anybody actually understood it.

Source: original

### `K-curious-2`: Emotion, natural register (top-up)

Tier 1. Style: `curious_questioning`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Think aloud while working toward a real question.

> Why is this step here at all? That is the question I keep coming back to. Somebody added it for a reason, presumably a good one, but nobody currently in the building remembers what that reason was. So do we keep it, or do we find out?

Source: original

### `K-empathetic-1`: Emotion, natural register (top-up)

Tier 1. Style: `empathetic_calm`. Target: 19 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Apologise to a frustrated user. Quieter is fine; stay fully voiced.

> I know this bit is annoying, and I am sorry. You have not done anything wrong. The file is fine, the format is fine, and it still will not go through, and that is entirely our fault rather than yours. Let me show you the workaround while we fix the actual problem.

Source: original

### `K-empathetic-2`: Emotion, natural register (top-up)

Tier 1. Style: `empathetic_calm`. Target: 17 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Reassure a new colleague with patience and your normal voice.

Speech form: single-speaker dialogue turn. Record only the displayed turn.

Dialogue context: A single speaker reassures a new colleague and invites questions.

> Take your time with it. Nobody expects you to have this figured out in the first week, and honestly most of us are still guessing about the parts we do not touch every day. Ask me anything, including things you think you should already know.

Source: original

### `K-punchy-1`: Emotion, natural register (top-up)

Tier 1. Style: `emphatic_punchy`. Target: 15 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Leave real silence between the short sentences and do not over-punch them.

> One number. One place. No arguing. You open it, you look, you know. That is the pitch. Everything else is detail.

Source: original

### `K-punchy-2`: Emotion, natural register (top-up)

Tier 1. Style: `emphatic_punchy`. Target: 16 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Give the three isolated words room, then keep the claim conversational.

> Faster. Cheaper. Simpler. Pick all three. Ninety seconds to set up, nothing to train, and it costs less than what you are already paying to be frustrated.

Source: original

### `K-awe-1`: Emotion, natural register (top-up)

Tier 1. Style: `awe_wonder`. Target: 20 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Do not sustain vowels, slow down, or become reverent. Describe something that genuinely impressed you.

> I did not expect to be affected by it, honestly. It is a building. I have seen buildings. But you come up the steps and the whole thing just opens above you, and for a second you cannot work out how any of it is standing up. I stood there like a tourist for about ten minutes.

Source: original

### `K-sorrow-1`: Emotion, natural register (top-up)

Tier 1. Style: `sorrow_grief`. Target: 19 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay restrained and matter-of-fact; do not perform sadness.

> We had the funeral on the Thursday. It rained, which everybody mentioned, as though it meant something. I keep expecting to see him at things. Not in a haunted way, just habit. Somebody makes a joke he would have liked and I turn slightly, and he is not there.

Source: original

### `K-anger-1`: Emotion, natural register (top-up)

Tier 1. Style: `anger_fierce`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay cold and controlled without raising your volume.

> No. I am not going to let that stand. You had the information in March, you sat on it until it became someone else's problem, and now you are in this room telling me it was unforeseeable. It was not unforeseeable. I forecast it, in writing, to you.

Source: original

### `K-tender-1`: Emotion, natural register (top-up)

Tier 1. Style: `tender_intimate`. Target: 19 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay close, soft, fully voiced, and clear.

> Come here. You are alright. Nothing that happened today is going to matter by Friday, I promise you that. We do not have to sort any of it out tonight, and nobody is cross with you. Just sit down for a bit and we will look at it in the morning.

Source: original

### `K-suspense-1`: Emotion, natural register (top-up)

Tier 1. Style: `suspense_hushed`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay quiet and urgent, with a voiced whisper and tension in the jaw rather than the volume.

> Do not turn the light on. Just listen for a second. There it is. That is the third time, and it is coming from under the floor, and I locked that door myself an hour ago. Whatever is down there knows we are standing here.

Source: original

### `K-playful-1`: Emotion, natural register (top-up)

Tier 1. Style: `playful_wry`. Target: 18 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Stay dry and amused; underplay it and let the timing do the work.

> Oh, wonderful. Another meeting to decide the agenda for the meeting. I shall bring snacks and a sleeping bag. Honestly at this point I have spent more of my adult life in that particular room than in my own kitchen, and the room has better chairs.

Source: original

### `K-triumph-1`: Emotion, natural register (top-up)

Tier 1. Style: `triumphant_declaratory`. Target: 17 seconds.

Direction: Say it the way you would in that situation. Keep your ordinary pitch, pace, and breath support; the emotion is already in the words. Sound pleased and generous, with tired relief rather than a proclamation.

> We actually did it. Eleven months, four false starts, and one weekend I would rather not discuss, and it is done, and it works. Look at the board. Every light is green. Go home, sleep, and do not answer your email until Monday.

Source: original

## Block L: Long-form plain reads (top-up)

### `L-01`: Long-form plain reads (top-up)

Tier 2. Style: `narration_neutral`. Target: 90 seconds.

Direction: One continuous take, plain reading throughout. If you stumble, keep going rather than restarting. Long plain reads yield several candidate windows from one recording, so this is the best value per minute in the whole top-up.

> I have been trying to work out when exactly the job changed, and I think it was the summer we moved buildings. Before that, everything happened in one room. If you needed to know something you turned around and asked, and if the person was not there you waited until they were. It was inefficient in every way that matters on paper, and it worked extremely well. Then we moved, and the team was split across two floors, and something quietly broke that took us a year to notice. Nobody stopped talking to each other. But the conversations became scheduled rather than accidental, and the accidental ones turned out to be the important ones. The problem someone mentions while waiting for the kettle is a different class of problem from the one they put on an agenda. What we lost was not communication. We had more of that than ever, most of it written down, most of it searchable. What we lost was the overhearing. You used to absorb half of what you needed to know without anyone deciding to tell you. I do not think there is a tool that fixes this, which is an awkward thing to believe in my line of work. The closest we have managed is a deliberate habit of saying things out loud that we would previously have said by accident, which sounds trivial and has been surprisingly hard to sustain.

Source: original

### `L-02`: Long-form plain reads (top-up)

Tier 2. Style: `narration_neutral`. Target: 92 seconds.

Direction: One continuous take, plain instructional reading at a normal pace. This is the exact register most of your demo narration will need, so it is the most directly useful recording in the top-up.

> Let me walk you through the whole setup, start to finish, at a normal pace. You begin on the workspaces screen. Click New in the top right. Give it a name you will still recognise in six months, which in practice means not calling it Test. The system will ask for a data source next, and this is the only part where you need somebody else's help, because you will need a connection string and most people do not have one to hand. Paste it in and click Check. This takes about twenty seconds. What it is doing is confirming three separate things. That the credentials work, that the tables you asked for are actually readable, and that nothing has a column type we cannot map onto our own. If any of those fail you get a specific message rather than a generic one, which I insisted on, because a generic connection error costs about half a day. Assuming all three pass, you will see a list of every table it found with a row count beside each. Sanity check that. If a table you expect to be enormous shows eleven rows, you are pointed at a stale copy, and it is much better to find that out now. Then choose the tables you actually need. Start with fewer than you think. You can always add more, and a smaller workspace opens faster every single time you use it.

Source: original
