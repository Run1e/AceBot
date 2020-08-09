import asyncio
import asyncpg

from config import DB_BIND

QUERIES = open('migrate.sql', 'r').read()


def log(connection, message):
	print(message)


async def main():
	db = await asyncpg.connect(DB_BIND)
	db.add_log_listener(log)

	async with db.transaction():
		await db.execute(QUERIES)

		# populate facts if empty
		if await db.fetchval('SELECT COUNT(id) FROM facts') == 0:
			for fact in facts.split('\n'):
				await db.execute('INSERT INTO facts (content) VALUES ($1)', fact)

		if await db.fetchval('SELECT COUNT(id) FROM linus_rant') == 0:
			for rant_and_hate in rants.split('\n'):
				split_rant = rant_and_hate.split('\t')

				if len(split_rant) != 2 or len(split_rant[1]) > 2000:
					continue
				
				await db.execute('INSERT INTO linus_rant (hate, rant) VALUES ($1, $2)', float(split_rant[0]), split_rant[1])


facts = """
If you somehow found a way to extract all of the gold from the bubbling core of our lovely little planet, you would be able to cover all of the land in a layer of gold up to your knees.
McDonalds calls frequent buyers of their food “heavy users.”
The average person spends 6 months of their lifetime waiting on a red light to turn green.
The largest recorded snowflake was in Keogh, MT during year 1887, and was 15 inches wide.
You burn more calories sleeping than you do watching television.
There are more lifeforms living on your skin than there are people on the planet.
Southern sea otters have flaps of skin under their forelegs that act as pockets. When diving, they use these pouches to store rocks and food.
In 1386 a pig in France was executed by public hanging for the murder of a child.
One in every five adults believe that aliens are hiding in our planet disguised as humans.
If you believe that you’re truly one in a million, there are still approximately 7,184 more people out there just like you.
A single cloud can weight more than 1 million pounds.
James Buchanan, the 15th U.S. president continuously bought slaves with his own money in order to free them.
There are more possible iterations of a game of chess than there are atoms in the observable universe.
The average person walks the equivalent of three times around the world in a lifetime.
Men are 6 times more likely to be struck by lightning than women.
Coca-Cola would be green if coloring wasn’t added to it.
You cannot snore and dream at the same time.
The world’s oldest piece of chewing gum is over 9,000 years old!
A coyote can hear a mouse moving underneath a foot of snow.
Bolts of lightning can shoot out of an erupting volcano.
New York drifts about one inch farther away from London each year.
A U.S. dollar bill can be folded approximately 4,000 times in the same place before it will tear.
A sneeze travels about 100 miles per hour.
Earth has traveled more than 5,000 miles in the past 5 minutes.
It would take a sloth one month to travel one mile.
10% of the World’s population is left handed.
A broken clock is right two times every day.
According to Amazon, the most highlighted books on Kindle are the Bible, the Steve Jobs biography, and The Hunger Games.
Bob Marley’s last words to his son before he died were “Money can’t buy life.”
A mole can dig a tunnel that is 300 feet long in only one night.
A hippo’s wide open mouth is big enough to fit a 4-foot-tall child in.
Chewing gum while you cut an onion will help keep you from crying.
If you were to stretch a Slinky out until it’s flat, it would measure 87 feet long.
Al Capone’s business card said he was a used furniture dealer.
There are more collect calls on Father’s Day than on any other day of the year.
Banging your head against a wall burns 150 calories an hour.
95% of people text things they could never say in person.
A crocodile can’t poke its tongue out.
It is physically impossible for pigs to look up into the sky.
Guinness Book of Records holds the record for being the book most often stolen from Public Libraries.
Drying fruit depletes it of 30-80% of its vitamin and antioxidant content.
A 2010 study found that 48% of soda fountains contained fecal bacteria, and 11% contained E. Coli.
9 out of 10 Americans are deficient in potassium.
Blueberries will not ripen until they are picked.
About 150 people per year are killed by coconuts.
About half of all Americans are on a diet on any given day.
A hardboiled egg will spin, but a soft-boiled egg will not.
Avocados are poisonous to birds.
Chewing gum burns about 11 calories per hour.
The number of animals killed for meat every hour in the U.S. is 500,000.
If you try to suppress a sneeze, you can rupture a blood vessel in your head or neck and die.
Celery has negative calories! It takes more calories to eat a piece of celery than the celery has in it to begin with. It’s the same with apples!
More people are allergic to cow’s milk than any other food.
Only 8% of dieters will follow a restrictive weight loss plan (like the HCG Drops Diet, garcinia cambogia diet).
Coconut water can be used as blood plasma.
The word “gorilla” is derived from a Greek word meaning, “A tribe of hairy women.”
Prisoners in Canadian war camps during World War II were treated so well that a lot of them didn’t want to leave when the war was over.
Gorillas burp when they are happy.
In New York, it is illegal to sell a haunted house without telling the buyer.
In 2006 someone tried to sell New Zealand on eBay. The price got up to $3,000 before eBay shut it down.
It is considered good luck in Japan when a sumo wrestler makes your baby cry.
A man from Britain changed his name to Tim Pppppppppprice to make it harder for telemarketers to pronounce.
A woman from California once tried to sue the makers of Cap’n Crunch, because the Crunch Berries contained “no berries of any kind.”
Apple launched a clothing line in 1986. It was described as a “train wreck” by others.
In Japan, crooked teeth are considered cute and attractive.
A Swedish woman lost her wedding ring, and found it 16 years later – growing on a carrot in her garden.
Donald Duck comics were banned from Finland because he doesn’t wear pants.
The chance of you dying on the way to get lottery tickets is actually greater than your chance of winning.
Cherophobia is the fear of fun.
The toothpaste “Colgate” in Spanish translates to “go hang yourself.”
Pirates wore earrings because they believed it improved their eyesight.
Human thigh bones are stronger than concrete.
Cockroaches can live for several weeks with their heads cut off, because their brains are located inside their body. They would eventually die from being unable to eat.
Scientists have tracked butterflies that travel over 3,000 miles.
To produce a single pound of honey, a single bee would have to visit 2 million flowers.
The population is expected to rise to 10.8 billion by the year 2080.
You breathe on average about 8,409,600 times a year.
More than 60,000 people are flying over the United States in an airplane right now.
Hamsters run up to 8 miles at night on a wheel.
A waterfall in Hawaii goes up sometimes instead of down.
A church in the Czech Republic has a chandelier made entirely of human bones.
Under the Code of Hammurabi, bartenders who watered down beer were punished by execution.
Our eyes are always the same size from birth, but our nose and ears never stop growing.
During your lifetime, you will produce enough saliva to fill two swimming pools.
You are 1% shorter in the evening than in the morning.
The elephant is the only mammal that can’t jump!
Most dust particles in your house are made from dead skin!
If 33 million people held hands, they could make it all the way around the equator.
Earth is the only planet that is not named after a god.
The bloodhound is the only animal whose evidence is admissible in court.
You are born with 300 bones, but by the time you are an adult you only have 206.
A ten-gallon hat will only hold ¾ of a gallon.
Just like fingerprints, everyone has different tongue prints.
ATMs were originally thought to be failures, because the only users were prostitutes and gamblers who didn’t want to deal with tellers face to face.
Of all the words in the English language, the word “set” has the most definitions. The word “run” comes in close second.
A “jiffy” is the scientific name for 1/100th of a second.
One fourth of the bones in your body are located in your feet.
111,111,111 × 111,111,111 = 12,345,678,987,654,321
Blue-eyed people tend to have the highest tolerance of alcohol.
A traffic jam lasted for more than 10 days, with cars only moving 0.6 miles a day.
Every year more than 2500 left-handed people are killed from using right-handed products.
More than 50% of the people in the world have never made or received a telephone call.
The cigarette lighter was invented before the match.
Sea otters hold hands when they sleep so that they do not drift apart.
The Golden Poison Dart Frog’s skin has enough toxins to kill 100 people.
The male ostrich can roar just like a lion.
Mountain lions can whistle.
Cows kill more people than sharks do.
Cats have 32 muscles in each of their ears.
A tarantula can live without food for more than two years.
The tongue of a blue whale weighs more than most elephants!
Ever wonder where the phrase “It’s raining cats and dogs” comes from? In the 17th century many homeless cats and dogs would drown and float down the streets of England, making it look like it literally rained cats and dogs.
It takes about 3,000 cows to supply enough leather for the NFL for only one year.
Male dogs lift their legs when they are urinating for a reason. They are trying to leave their mark higher so that it gives off the message that they are tall and intimidating.
A hummingbird weighs less than a penny.
An ostrich’s eye is bigger than its brain.
Dogs are capable of understanding up to 250 words and gestures and have demonstrated the ability to do simple mathematical calculations.
A sheep, a duck and a rooster were the first passengers in a hot air balloon.
Birds don’t urinate.
A flea can jump up to 200 times its own height. That is the equivalent of a human jumping the Empire State Building.
There are 5 temples in Kyoto, Japan that have blood stained ceilings. The ceilings are made from the floorboards of a castle where warriors killed themselves after a long hold-off against an army. To this day, you can still see the outlines and footprints.
There is a snake, called the boomslang, whose venom causes you to bleed out from every orifice on your body. You may even turn blue from internal bleeding, and it can take up to 5 days to die from the bleeding.
Saturn’s density is low enough that the planet would float in water.
68% of the universe is dark energy, and 27% is dark matter; both are invisible, even with our powerful telescopes. This means we have only seen 5% of the universe from earth.
The founders of Google were willing to sell Google for $1 million to Excite in 1999, but Excite turned them down. Google is now worth $527 Billion.
In the past 20 years, scientists have found over 1,000 planets outside of our solar system.
There are 60,000 miles of blood vessels in the human body.
If a pregnant woman has organ damage, the baby in her womb sends stem cells to help repair the organ.
If you started with $0.01 and doubled your money every day, it would take 27 days to become a millionaire.
Only one person in two billion will live to be 116 or older.
A person can live without food for about a month, but only about a week without water.
On average, 12 newborns will be given to the wrong parents daily.
You can’t kill yourself by holding your breath.
Human birth control pills work on gorillas.
There are no clocks in Las Vegas gambling casinos.
Beetles taste like apples, wasps like pine nuts, and worms like fried bacon.
Months that begin on a Sunday will always have a “Friday the 13th.”
The placement of a donkey’s eyes in its head enables it to see all four feet at all times!
Some worms will eat themselves if they can’t find any food!
Dolphins sleep with one eye open!
It is impossible to sneeze with your eyes open.
In France, it is legal to marry a dead person.
Russia has a larger surface area than Pluto.
There’s an opera house on the U.S.–Canada border where the stage is in one country and half the audience is in another.
The harder you concentrate on falling asleep, the less likely you are to fall asleep.
You can’t hum while holding your nose closed.
Women have twice as many pain receptors on their body than men. But a much higher pain tolerance.
There are more stars in space than there are grains of sand on every beach in the world.
For every human on Earth there are 1.6 million ants. The total weight of all those ants, however, is about the same as all the humans.
On Jupiter and Saturn it rains diamonds.
It is impossible to lick your elbow.
A shrimp’s heart is in its head.
People say "Bless you" when you sneeze because when you sneeze, your heart stops for a millisecond.
In a study of 200,000 ostriches over a period of 80 years, no one reported a single case where an ostrich buried its head in the sand.
Rats and horses can’t vomit.
If you sneeze too hard, you can fracture a rib.
If you keep your eyes open by force when you sneeze, you might pop an eyeball out.
Rats multiply so quickly that in 18 months, two rats could have over a million descendants.
Wearing headphones for just an hour will increase the bacteria in your ear by 700 times.
In every episode of Seinfeld there is a Superman somewhere.
35% of the people who use personal ads for dating are already married.
23% of all photocopier faults worldwide are caused by people sitting on them and photocopying their butts.
Most lipstick contains fish scales.
Over 75% of people who read this will try to lick their elbow.
A crocodile can’t move its tongue and cannot chew. Its digestive juices are so strong that it can digest a steel nail.
Money notes are not made from paper, they are made mostly from a special blend of cotton and linen. In 1932, when a shortage of cash occurred in Tenino, Washington, USA, notes were made out of wood for a brief period.
The Grammy Awards were introduced to counter the threat of rock music. In the late 1950s, a group of record executives were alarmed by the explosive success of rock ‘n’ roll, considering it a threat to “quality” music.
Tea is said to have been discovered in 2737 BC by a Chinese emperor when some tea leaves accidentally blew into a pot of boiling water. The tea bag was introduced in 1908 by Thomas Sullivan.
Over the last 150 years the average height of people in industrialized nations has increased about 4 inches. In the 19th century, American men were the tallest in the world, averaging 5′6″. Today, the average height for American men is 5′7″, compared to 5′8″ for Swedes, and 5′8.5″ for the Dutch. The tallest nation in the world is the Watusis of Burundi.
In 1955 the richest woman in the world was Mrs. Hetty Green Wilks, who left an estate of $95 million in a will that was found in a tin box with four pieces of soap. Queen Elizabeth of Britain and Queen Beatrix of the Netherlands count under the 10 wealthiest women in the world.
Joseph Niepce developed the world’s first photographic image in 1827. Thomas Edison and William Kennedy-Laurie Dickson introduced the film camera in 1894. But the first projection of an image on a screen was made by a German priest. In 1646, Athanasius Kircher used a candle or oil lamp to project hand-painted images onto a white screen.
In 1935 a writer named Dudley Nichols refused to accept the Oscar for his movie The Informer because the Writers Guild was on strike against the movie studios. In 1970 George C. Scott refused the Best Actor Oscar for Patton. In 1972 Marlon Brando refused the Oscar for his role in The Godfather.
The system of democracy was introduced 2,500 years ago in Athens, Greece. The oldest existing governing body operates in Althing, Iceland. It was established in 930 AD.
If the amount of water in your body is reduced by just 1%, you’ll feel thirsty. If it is reduced by 10%, you’ll die.
According to a study by the Economic Research Service, 27% of all food production in Western nations ends up in garbage cans. Yet, 1.2 billion people are underfed – the same number of people who are overweight.
Camels are called “ships of the desert” because of the way they move, not because of their transport capabilities. A dromedary has one hump and a Bactrian camel two humps. The humps are used as fat storage. Thus, an undernourished camel will not have a hump.
In the Durango desert in Mexico, there’s a creepy spot called the “Zone of Silence.” You can’t pick up clear TV or radio signals. And locals say fireballs sometimes appear in the sky.
Ethernet is a registered trademark of Xerox, Unix is a registered trademark of AT&T.
Bill Gates’ first business was Traf-O-Data, a company that created machines which recorded the number of vehicles passing a given point on a road.
Uranus’ orbital axis is tilted at over 90 degrees.
The famed U.S. Geological Survey astronomer Mr. Eugene Shoemaker trained the Apollo astronauts about craters, but never made it into space. Mr. Shoemaker had wanted to be an astronaut but was rejected because of a medical problem. His ashes were placed on board the Lunar Prospector spacecraft before it was launched on January 6, 1998. NASA crashed the probe into a crater on the moon in an attempt to learn if there is water on the moon.
Outside the U.S., Ireland is the largest software producing country in the world.
The first fossilized specimen of Australopithecus afarenisis was named Lucy after the paleontologists’ favorite song “Lucy in the Sky with Diamonds,” by the Beatles.
FIGlet, an ASCII font converter program, stands for Frank, Ian and Glenn’s LETters.
Every human spent about half an hour as a single cell.
Every year about 98% of atoms in your body are replaced.
Hot water is heavier than cold water.
Plutonium – first weighed on August 20th, 1942, by University of Chicago scientists Glenn Seaborg and his colleagues – was the first man-made element.
If you went out into space, you would explode before you suffocated because there’s no air pressure.
The radioactive substance Americium-241 is used in many smoke detectors.
The original IBM-PCs, that had hard drives, referred to the hard drives as Winchester drives. This is due to the fact that the original Winchester drive had a model number of 3030. This is, of course, a Winchester firearm.
Sound travels 15 times faster through steel than through the air.
On average, half of all false teeth have some form of radioactivity.
Only one satellite has been ever been destroyed by a meteor: the European Space Agency’s Olympus in 1993.
Starch is used as a binder in the production of paper. It is the use of a starch coating that controls ink penetration when printing. Cheaper papers do not use as much starch, and this is why your elbows get black when you are leaning over your morning paper.
Sterling silver is not pure silver. Because pure silver is too soft to be used in most tableware it is mixed with copper in the proportion of 92.5% silver to 7.5% copper.
A ball of glass will bounce higher than a ball of rubber. A ball of solid steel will bounce even higher.
A chip of silicon a quarter-inch square has the capacity of the original 1949 ENIAC computer, which occupied a city block.
An ordinary TNT bomb involves atomic reaction and, thus, could be called an atomic bomb. What we call an A-bomb involves nuclear reactions and should be called a nuclear bomb.
At a glance, the Celsius scale makes more sense than the Fahrenheit scale for temperature measuring. But its creator, Anders Celsius, was an oddball scientist. When he first developed his scale, he made the freezing of water 100 degrees and the boiling 0 degrees. No one dared point this out to him, so fellow scientists waited until Celsius died to change the scale.
At a jet plane’s speed of 620 mph, the length of the plane becomes one atom shorter than its original length.
The first full moon to occur on the winter solstice, December 22, commonly called the first day of winter, happened in 1999. Since a full moon on the winter solstice occurred in conjunction with a lunar perigee (point in the moon’s orbit that is closest to Earth), the moon appeared about 14% larger than it does at apogee (the point in its elliptical orbit that is farthest from Earth). Since the Earth is also several million miles closer to the sun at that time of the year than in the summer, sunlight striking the moon was about 7% stronger making it brighter. Also, this was the closest perigee of the Moon of the year since the moon’s orbit is constantly deforming. In places where the weather was clear and there was a snow cover, even car headlights were superfluous.
According to security equipment specialists, security systems that utilize motion detectors won’t function properly if walls and floors are too hot. When an infrared beam is used in a motion detector, it will pick up a person’s body temperature of 98.6 °F compared to the cooler walls and floor. If the room is too hot, the motion detector won’t register a change in the radiated heat of that person’s body when it enters the room and breaks the infrared beam. Your home’s safety might be compromised if you turn your air conditioning off or set the thermostat too high while on summer vacation.
Western Electric successfully brought sound to motion pictures and introduced systems of mobile communications which culminated in the cellular telephone.
On December 23, 1947, Bell Telephone Laboratories in Murray Hill, N.J., held a secret demonstration of the transistor which marked the foundation of modern electronics.
The wick of a trick candle has small amounts of magnesium in them. When you light the candle, you are also lighting the magnesium. When someone tries to blow out the flame, the magnesium inside the wick continues to burn and, in just a split second (or two or three), relights the wick.
Ostriches are often not taken seriously. They can run faster than horses, and the males can roar like lions.
Seals used for their fur get extremely sick when taken aboard ships.
Sloths take two weeks to digest their food.
Guinea pigs and rabbits can’t sweat.
The pet food company Ralston Purina recently introduced, from its subsidiary Purina Philippines, power chicken feed designed to help roosters build muscles for cockfighting, which is popular in many areas of the world. According to the Wall Street Journal, the cockfighting market is huge: The Philippines has five million roosters used for exactly that.
The porpoise is second to man as the most intelligent animal on the planet.
Young beavers stay with their parents for the first two years of their lives before going out on their own.
Skunks can accurately spray their smelly fluid as far as ten feet.
Deer can’t eat hay.
Gopher snakes in Arizona are not poisonous, but when frightened they may hiss and shake their tails like rattlesnakes.
On average, dogs have better eyesight than humans, although not as colorful.
The duckbill platypus can store as many as six hundred worms in the pouches of its cheeks.
The lifespan of a squirrel is about nine years.
North American oysters do not make pearls of any value.
Many sharks lay eggs, but hammerheads give birth to live babies that look like very small duplicates of their parents. Young hammerheads are usually born headfirst, with the tip of their hammer-shaped head folded backward to make them more streamlined for birth.
Gorillas sleep as much as fourteen hours per day.
A biological reserve has been made for golden toads because they are so rare.
There are more than fifty different kinds of kangaroos.
Jellyfish like salt water. A rainy season often reduces the jellyfish population by putting more fresh water into normally salty waters where they live.
The female lion does ninety percent of the hunting.
The odds of seeing three albino deer at once are one in seventy-nine billion, yet one man in Boulder Junction, Wisconsin, took a picture of three albino deer in the woods.
Cats often rub up against people and furniture to lay their scent and mark their territory. They do it this way, as opposed to the way dogs do it, because they have scent glands in their faces.
Cats sleep up to eighteen hours a day, but never quite as deep as humans. Instead, they fall asleep quickly and wake up intermittently to check to see if their environment is still safe.
Catnip, or Nepeta cataria, is an herb with nepetalactone in it. Many think that when cats inhale nepetalactone, it affects hormones that arouse sexual feelings, or at least alter their brain functioning to make them feel “high.” Catnip was originally made, using nepetalactone as a natural bug repellant, but roaming cats would rip up the plants before they could be put to their intended task.
The nematode Caenorhabditis elegans ages the equivalent of five human years for every day they live, so they usually die after about fourteen days. When stressed, though, the worm goes into a comatose state that can last for two or more months. The human equivalent would be to sleep for about two hundred years.
You can tell the sex of a horse by its teeth. Most males have 40, females have 36.
The 57 on Heinz ketchup bottle represents the varieties of pickle the company once had.
Your stomach produces a new layer of mucus every two weeks – otherwise it will digest itself.
The Declaration of Independence was written on hemp paper.
A raisin dropped in a glass of fresh champagne will bounce up and down continuously from the bottom of the glass to the top.
Susan Lucci is the daughter of Phyllis Diller.
315 entries in Webster’s 1996 Dictionary were misspelled.
During the chariot scene in “Ben-Hur” a small red car can be seen in the distance.
Warren Beatty and Shirley MacLaine are brother and sister.
Orcas (killer whales) kill sharks by torpedoing up into the shark’s stomach from underneath, causing the shark to explode.
Donald Duck comics were banned from Finland because he doesn’t wear any pants.
Ketchup was sold in the 1830s as medicine.
Upper and lower case letters are named “upper” and “lower” because in the time when all original print had to be set in individual letters, the “upper case” letters were stored in the case on top of the case that stored the smaller, “lower case” letters.
Leonardo da Vinci could write with one hand and draw with the other at the same time.
Because metal was scarce, the Oscars given out during World War II were made of wood.
The name Wendy was made up for the book Peter Pan, there was never a recorded Wendy before!
There are no words in the dictionary that rhyme with: orange, purple, and silver!
Leonardo Da Vinci invented scissors.
A tiny amount of liquor on a scorpion will make it instantly go mad and sting itself to death.
The mask used by Michael Myers in the original “Halloween” was a Captain Kirk mask painted white.
If you have three quarters, four dimes, and four pennies, you have $1.19. You also have the largest amount of money in coins without being able to make change for a dollar.
The glue on Israeli postage stamps is certified kosher.
Guinness Book of Records holds the record for being the book most often stolen from Public Libraries.
Astronauts are not allowed to eat beans before they go into space because passing wind in a space suit damages them.
The word “queue” is the only word in the English language that is still pronounced the same way when the last four letters are removed.
“Almost” is the longest word in the English language with all the letters in alphabetical order.
“Rhythm” is the longest English word without a vowel.
There is a city called Rome on every continent.
It’s against the law to have a pet dog in Iceland.
Your heart beats over 100,000 times a day.
Horatio Nelson, one of England’s most illustrious admirals was throughout his life, never able to find a cure for his sea-sickness.
The skeleton of Jeremy Bentham is present at all important meetings of the University of London.
Right-handed people live, on average, nine years longer than left-handed people.
Your ribs move about 5 million times a year, every time you breathe!
One quarter of the bones in your body, are in your feet!
The first known transfusion of blood was performed as early as 1667, when Jean-Baptiste, transfused two pints of blood from a sheep to a young man.
Fingernails grow nearly 4 times faster than toenails!
Women blink nearly twice as much as men.
Adolf Hitler was a vegetarian, and had only one testicle.
Honey is one of the only foods that do not spoil. Honey found in the tombs of Egyptian pharaohs has been tasted by archaeologists and found edible.
On average a hedgehog’s heart beats 300 times a minute.
More people are killed each year from bees than from snakes.
The average lead pencil will draw a line 35 miles long or write approximately 50,000 English words.
Camels have three eyelids to protect themselves from blowing sand.
The six official languages of the United Nations are: English, French, Arabic, Chinese, Russian and Spanish.
It’s against the law to burp, or sneeze in a church in Nebraska, USA.
The longest recorded flight of a chicken is 13 seconds.
Queen Elizabeth I. regarded herself as a paragon of cleanliness. She declared that she bathed once every three months, whether she needed it or not.
Slugs have 4 noses.
Owls are the only birds who can see the color blue.
A man named Charles Osborne had the hiccups for 69 years!
A giraffe can clean its ears with its 21-inch tongue!
The average person laughs 10 times a day!
If you yelled for 8 years, 7 months and 6 days you would have produced enough sound energy to heat one cup of coffee.
If you farted consistently for 6 years and 9 months, enough gas is produced to create the energy of an atomic bomb.
The human heart creates enough pressure when it pumps out to the body to squirt blood 30 feet.
A pig’s orgasm lasts 30 minutes.
The male praying mantis cannot copulate while its head is attached to its body. The female initiates sex by ripping the male’s head off.
The flea can jump 350 times its body length. It’s like a human jumping the length of a football field.
The catfish has over 27,000 taste buds.
Some lions mate over 50 times a day.
Butterflies taste with their feet.
The strongest muscle in the body is the tongue.
A cat’s urine glows under a black light.
Starfish have no brains.
Polar bears are left-handed.
Humans and dolphins are the only species that have sex for pleasure.
"""

rants = '''
0.548215650637363	WRONG. Alan, you're not getting it. Loading firmware as part of suspend/resume is WRONG.
0.886731624967559	What the heck is your problem? Go back and read it. If it wasn't loaded before, THEN IT WASN'T WORKING BEFORE EITHER! ... Why the hell do you keep on harping on idiotic issues? Stop being a moron, just repeat after me: A caching firmware loader fixes all these issues and is simple to boot. Stop the idiotic blathering already.
0.87595585276089	Why do you make up all these idiotic theoretical cases that nobody cares about and has no relevance what-so-ever for the 99%? Seriously? It's just stupid. ... You seem to *intentionally* be off in some random alternate reality that is not relevant to anybody else, or to the actual reported problems at hand.
0.864581255361391	"Whjat the f*ck is the logic there? Just fix the *obvious* breakage in BLKROSET. It's clearly what the code *intends* to do, it just didn't check for ENOIOCTLCMD. ... It's a DISEASE how you seem to think that ""we have ugly mistakes in the kernel, SO LET'S ADD ANOTHER ONE"". That's not how we do things. We *fix* things, instead of making things even *worse*. Stop this insanity from spreading, instead of making it spread more!"
0.834850369775705	You are the one who seems to just want to add hack upon hack to things. THAT is what I really hate. It's not only in bad taste, it *will* come back and bite us some day.
0.88118300765669	"Hell no! Why do you send me this sh*t? The ""Use NMI instead of REBOOT_VECTOR"" commit has been reported to not work AT ALL. It was totally broken... yet you send me this KNOWN BROKEN CRAP. And yes, I checked. The version you sent me is the f*cked one. I was hoping that you would have fixed it up. But no. In short, you didn't merge the fix, and yet you sent me a patch series that was *known* to be broken for the last three+ weeks! ... Why? WHAT THE F*CK HAPPENED, INGO? Yes, I'm angry as hell. Shit like this should NOT happen.  I don't want people sending me known-buggy pull requests."
0.798715158593696	"Mark, I pulled this, but I was *this* close to unpulling it because it's such an unholy mess. You seem to do the crazy ""daily pull"" crap that NOBODY IS EVER SUPPOSED TO DO. There are lots of totally pointless ... merge commits, and no, that's not ok.... Just don't do it. There's no excuse. The *only* time you should merge is when a sub lieutenant asks you to - and if you have people who work with you and ask you to do pointless merges almost every day, just tell them to shut the f*ck up already!...But dammit, don't then do development on top of that kind of crap - use that branch *only* for linux-next, not for anything else, and don't ask me to pull that polluted piece of sh*t. ...But never *ever* have those stupid pointless ""Merge remote-tracking branch 'regulator/for-linus' into regulator-next"" in the branch you actually use for development, and the branch you send to me."
0.742679263504761	No it's not. Please fix your crappy script. First off, that '#' is wrong. It should be a space.
0.69741327450243	...You did *two* of the merges within hours of each other! ... That's just crazy. The fact that you then say that you have some kind of *excuse* for that craziness is just sad. Stop doing that. It's stupid. It just makes it harder for everybody to see what you are doing. ...Can't you see how crazy that is?
0.638953310781119	"Stop being a moron. Go back and read the ""nobody can work with you""."
0.690869795819343	That statement is so nonsensical that I can't get past it. When you understand why it is nonsensical, you understand why the bit is cleared. Feel free to bring this up again without that idiotic statement as an argument.
0.676388377515012	So stop spouting garbage.
0.856006572922634	.. And how the f*^& did you imagine that something like chrome would do that? You need massive amounts of privileges, and it's a total disaster in every single respect. Stop pushing crap. No, ptrace isn't wonderful, but your LSM+auditing idea is a billion times worse in all respects. ... THERE IS NO WAY IN HELL YOU CAN EVER FIX LSM+AUDIT TO BE USABLE! Stop bothering to even bring it up. It's dead, Jim.
0.749374153119353	"And this is just insanity. The ""barrier()"" cannot *possibly* do anything sane. If it really makes a difference, there is again some serious problem with the whole f*cking thing. NAK on the patch until sanity is restored. This is just total voodoo programming."
0.904115248323772	This still doesn't make sense. Why do that stupid allocation? Why not just move the entry? Why doesn't just the sane approach work? What the f*^& does that pci_stop_bus_device() function do ...And if it does anything else, it should damn well stop doing that. The *exact* same loop is then apparently working for the virtual device case, so what the hell is going on that it wouldn't work for the physical one? What's the confusion? Why all the crazy idiotic code that makes no sense?
0.786556214631599	...which at least isn't butt ugly. ... Who is in charge of the whole 'is_virtfn' mess? How realistic is it to fix that crud?
0.76256174428619	Ugh. Ok, so that's a disgusting hack, but it's better than messing up the generic PCI subsystem. At least it's a disgusting hack in the IOV code.
0.912858630549809	I think this patch is horrible, and broken. And making the feature a config option is just stupid.
0.890787561970504	I hate this patch. Why? Because mindless checks like this would just lead to people making things worse and intermixing spaces there instead.
0.736764336925693	I never *ever* want to see this code ever again. Sorry, but last time was too f*cking painful. 
0.804935503438898	Duh. That is just broken. ... That's just stupid. 
0.909745695099211	"Ingo, stop with the stupid denialism. NOBODY likes that name. NOBODY. It's wrong. It's stupid. It sounds like a stronger ""unlikely()"", and it simply IS NOT. So rename it already. ..."
0.907523156483724	"There's two of those *stupid* merges that have no reason for existing, no explanation, and are just ugly. Don't do this, guys! ... Christ. I really don't like stupid unnecessary merges. ... The above is really just a f*cking abomination, and says ""somebody is doing something horribly wrong""."
0.461319620589342	"Congratulations, you seem to have found a whole new and unique way of screwing up ;) Linus ""my mom called me 'special' too"" Torvalds"
0.401778212265373	Oh christ. This is exactly what the scheduler has ALWAYS ALREADY DONE FOR YOU. ... Stop doing it. You get *zero* advantages from just doing what the scheduler natively does for you, and the scheduler does it *better*.
0.889326630429146	"Ugh. But my patch was crap. It fixed up ""arg"", but it *should* have fixed up ""cmd"". Stupid."
0.782515024394104	Stop right there. ... This is about your patch BREAKING EXISTING BINARIES. So stop the f*&^ing around already. The patch was shown to be broken, stop making excuses, and stop blathering. End of story. Binary compatibility is more important than *any* of your patches. If you continue to argue anything else or making excuses, I'm going to ask people to just ignore your patches entirely. Seriously. ... Dammit, I'm continually surprised by the *idiots* out there that don't understand that binary compatibility is one of the absolute top priorities. ... Breaking existing binaries ... is just about the *worst* offense any kernel developer can do. Because that shows that they don't understand what the whole *point* of the kernel was after all. We're not masturbating around with some research project.  We never were. Even when Linux was young, the whole and only point was to make a *usable* system. It's why it's not some crazy drug-induced microkernel or other random crazy thing. Really.
0.821506550701163	Christ. This one is too ugly to live. I'm not pulling crap like this. It's f*^&ing stupid to take a lock, calculate a bitqueue, and just generally be an absolute ass-hat about things for waiting for a bit that is already set 99.999% of the time.
0.606512526777025	"Umm. I think your argument is totally braindead and wrong. My counter-argument is very simple: ""So what?"""
0.787343455864816	"Sorry, you're wrong. And Rafael *told* you why you are wrong, and you ignored him and talked about ""exec"" some more. So go back and read Rafael's email. ... So please, read the emails. People actually *agree* that the name may be a bit misleading, but instead of harping on bogus issues, just read the emails from people like Rafael about it. So STOP with this idiocy already. ... Seriously. Get that through your head already."
0.842510012478088	"So I have to say, I hate this entire series. ... So quite frankly, I think the whole series is total and utter garbage. And there isn't even any *explanation"" for the garbage. You say that you are unifying things, but dammit, in order to unify them you end up *adding*new*f&^#ing*code*. ... So a honking big NAK on this whole series unless you can explain with numbers and show with numbers what the advantage of the abortion is."
0.859698668648547	Ugh, this is disgusting.
0.903355526226076	"Stop these idiotic games already! ... Your moronic ""let's change the test to something else"" is entirely and utterly misguided and totally misses the point. ... Stop the idiocy already. How hard is it to understand? How many times do people have to tell you? ... Rafael, please consider everything along these *IDIOTIC* lines completely NAK'ed. In fact, until Stephen starts showing any sign of understanding that it's not about just some random small detail, just ignore anything and everything from him. Stephen, you've been told multiple times that that WARN_ON() is correct. Until you understand that, just stop sending these entirely random patches that change it to something completely wrong. How hard can it be to understand that you cannot and must not load firmware when the system isn't up-and-running. And *dammit*, the fact that you send these kinds of completely nonsensical patches ... all you are showing is that you don't understand the problem. Stop, think, and read the emails that have been in this thread and that have explained how it *could* be solved. Until you do that, any patch you send is just worthless. Really."
0.863940800346905	Ugh. This is getting really ugly. ... because quite frankly, the whole spinunlock inlining logic is *already* unreadable, and you just made it worse.
0.892596967274178	... Why do I call it a total disaster? ... More importantly, they are both IDENTICALLY BAD. They are crap because: ... Doing a function call for these things is stupid. ...
0.862346378760911	"... I will not be pulling this tree at all. It's pure and utter shit, and I wonder how long (forever?) this has been going on. ...the thing that makes me go ""uhhuh, no way in *hell* should I pull this"" is that you have apparently totally broken all sign-offs. Avi, you ABSOLUTELY MUST NOT rebase other peoples commits. That's a total no-no. And one thing I notice when I look through the commits is that you have totally broken the Signed-off-by: series in the process, exactly because what you do is crap, crap, CRAP. ... That's simply not true in your tree. Maybe because you have rebased other peoples (Alexander's) commits? I see commits where the sign-off ends with Alexander, but then the committer is you. WTF? Fix your f*cking broken shit *now*. I'm not pulling crap like this. And it makes me unhappy to realize that this has probably happened a long time and I haven't even noticed. The whole ""you MUST NOT rebase other peoples commits"" is the thing I've been telling people for *years* now. Why the hell is it still going on?"
0.75520484432542	Ugh: ... Can we please move that abortion into arch/powerpc/? Instead of making generic code even uglier..
0.789545469942151	"Your original email used ""torv...@osdl.org"", which goes into a kind-of-black hole. Please fix whatever crazy-old address book you have - that address is old, old, old. Oh, and your *new* email had totally broken email headers too. WTF? That ... is just pure and utter garbage. What the hell is wrong with your email setup? When I reply to that email, I sure as hell want to reply to *you*, not to *me*. So fix your email, right now it's terminally broken. Will look at the pull requests now that I actually see them, and when I'm over being upset by your idiotic email issues."
0.764455381312007	Finally, people - your merge messages suck. Leaving the list of conflicting files without talking about what the conflict actually was is *not* a good merge message. Len, you're not the only one that does this, but it is yet another reason why I absolutely detest some of the merges I see: they are just very uninformative, and don't add anything useful to the tree - quite the reverse. They hide a problem, without actually talking about what the problem was. ...And yes, sometimes my merge messages suck too (although I've tried very hard to become better at them).
0.838975677701874	Grr. Most of these patches have the same stupid problem: why the *hell* do you repeat the single-line top-level description in both the Subject line and the body of the email? It only results in stupid duplicate lines in the commit logs. This is a disease. I don't know who the heck started doing it, but it's WRONG. It's stupid. What broken piece-of-shit tool is it that does this braindamage? Fix it. Stop sending these broken commit messages to people. I'm grumpy, yes, because this is a common problem. I see it all over the place, and it makes our commit logs look f*cking retarded. ...
0.854350160726805	"... Why has this been explicitly designed to be as ugly as humanly possible, and to be so inconvenient to parse too? ... So here's a serious suggestion: aim for ""line oriented"". ... ...That's stupid. Don't do it. ...Because this is just pure and utter *shit*: ...This part gets a big NAK from me. I don't see the point of this. It's pure crap. There's no advantage. And the ""use an uint64_t"" is a classic case of just being a f*cking moron. ...This is the kind of thinking and code that just makes me go ""No way, not today, not ever"". It's *stupid*."
0.885942456755531	"Oh, *HELL*NO*! It's a fucking disaster in ""Oh, one notifier was broken, SO LET'S ADD ANOTHER RANDOM ONE TO FIX THAT"". The definition of insanity is doing the same thing over and over and thinking you get a different result. Let's not do that kind of idiotic thing. Notifiers are evil crap. Let's make *fewer* of them, not add yet-another-random-notifier-for-some-random-reason. F*ck me, but how I hate those random notifiers. And I hate people who add them willy nilly."
0.587876133057311	...So stop complaining. Reverts really *are* just patches, Greg is 100% right, and you are simply wrong. ...and the fact that you *continue* to complain just makes you look stupid.
0.757311538194661	You're a fucking moron. ... So just reverting it from stable, *WITHOUT LEARNING THE LESSON*, is not a no-op at all, it's a sign of being a f*cking moron. I'm stupider for just reading your email. Go away.
0.810709046585318	Stop the idiotic arguing already.
0.879826077432954	"Please don't continue to spread this total bogosity. ...That's a total idiotic lie by C++ apologists, and I hate hearing it repeated over and over again. And it really *is* a lie. ... Which is clearly insane, but is also technically simply *wrong*. ... Which is utter and complete bullshit, and any amount of brains would have realized that ... It has always been just nothing but a moronic hang-up, and it has always been *wrong*. So don't spread that lie. It was wrong. ... which is pure and utter garbage. And then they lie, and claim that their *weaker* type system NULL is ""stronger"". Pure idiocy."
0.7454519550857	"...And a C++ person who says that ""(vodi *)0"" is just any ""void *"" is a *fucking*moron*, ...There is absolutely *zero* excuse for the idiotic traditional C++ brain damage of saying ""NULL cannot be '(void *)0', because 'void *' will warn"". Anybody who says that is lying. ... The C++ people? They are morons, and they never got it, and in fact they spent much of their limited mental effort arguing against it. ... The whole ""it's a stronger type system, so NULL has to be 0"" is pure and utter garbage. It's wrong. It's stupid. ... Yeah, I'm not a fan of C++. It's a cruddy language."
0.74904014484169	They may be readable, but they are total shit. ... So no. Hell no.
0.748839826430043	And if you cannot understand what tens of people have tried to explain to you, you are just f*cking stupid.
0.911366092099658	Ugh, I personally hate it. ... Your suggested format just sucks, and has the worst of all worlds.
0.874043841839301	...This is wrong. Or at least stupid.
0.663332578025401	"Oh christ. What insane version of gcc is that? Can you please make a gcc bug-report? ... is just so fricking stupid that it's outright buggy. That's just crazy. It's demented. It's an ""and"" with all bits set."
0.883293343598317	"...which is obviously completely bogus - it's even broken the constant. Your address simplification does something horribly bad. ... That's a totally worthless instruction. ... That "",1"" is completely bogus, and I don't understand why the tools show that idiotic format to begin with. It's pure garbage. It adds zero information.... That ""0x0"" is more useless garbage in the same vein. ... Btw, don't get me wrong. I really like the changes. "
0.734517328092954	Oh christ, I also cannot be bothered to continue arguing with you since you seemingly randomly drop other people from the discussion. So don't expect any more replies from me.
0.595846158103879	"Don't try to change the rules because you think you are ""clever"". You're only making things worse."
0.867569373727191	So? Even if we hadn't had this bug before (we have), your argument is utter crap. ...Stop arguing for crap.
0.819729553536058	I absolutely detest these types. I realize that we already have a few users, but just looking at these diffs *hurts*. It's disgusting.
0.665562813552309	Ok, this code is a rats nest. ... The code is crazy. It's an unreadable mess. Not surprising that it then also is buggy.... Looking at the code, I don't think it has been written by a human. ... Some of that code is clearly pure garbage. ... In fact, it's *all* crap. 
0.761321461069052	NAK NAK NAK. Ingo, please don't take any of these patches if they are starting to make NUMA scheduling be some arch-specific crap. Peter - you're way off base. You are totally and utterly wrong for several reasons: ...so making some arch-specific NUMA crap is *idiotic*. Your argument ...is pure crap. ... Christ, people. ...is just f*cking moronic. ... Stop the idiocy. ...
0.700387815702233	Wrong. ... so you're just full of it. ... Checking the MCE data is stupid and wrong. Stop doing it, and stop making idiotic excuses for it. ...you are just doing moronic things. Stop doing stupid things.
0.919955997047451	Ugh. No. That is too disgusting for words.
0.801731111695407	"*NEITHER* of your points actually address my issue. ... IOW, why the hell do you set a name that is so useful that no sane person would ever want to use it? ... So let me be more blunt and direct: which part of ""that's f*cking stupid"" do you disagree with? So instead of making drivers do stupid things because you've made the input layer names so damn useless, why don't you make the input layer use better naming? Doesn't that seem to be the *smart* thing to do?"
0.69095835350407	I'll let you think about just how stupid that comment was for a moment.
0.766463779563815	Ugh, looking more at the patch, I'm getting more and more convinces that it is pure and utter garbage. ... WTF? ... This is crap, guys. Seriously. Stop playing russian rulette with this code.
0.894960333111712	No, that's just crazy. Now you make broken shit code work, and then you break the *correct* code... Just face it: if somebody doesn't have an interrupt-time function pointer, they need to rethink their code. It's a mistake. It's broken shit. Why pander to crap? 
0.922208525355724	"This is too damn ugly. These kinds of ""conditionally take lock"" things are always just bugs waiting to happen. Don't do it. ... These kinds of ""bool lock"" crap things have to die. They are *wrong*. They are a sign of bad locking rules."
0.753725152871591	Umm. That just smells like BS to me. ... Also, your protection claim seems to be invalidated by the actual code. ... So your claim that it hedges around it by looking at the inquiry data is pure crap. It's simply not true. ... So no, I simply don't see the careful testing or the checking that you claim exists.
0.914236858796736	This is horrible, I think. NAK NAK NAK. ... So don't do this. It's stupid. ... I absolutely *detest* patches like this that make *practical* security worse, in the name of some idiotic theoretical worry that nobody has any reason to believe is real.
0.6210100248237	Kay, this needs to be fixed. ... Of course, I'd also suggest that whoever was the genius who thought it was a good idea to read things ONE F*CKING BYTE AT A TIME with system calls for each byte should be retroactively aborted. Who the f*ck does idiotic things like that? How did they noty die as babies, considering that they were likely too stupid to find a tit to suck on?
0.76845286548124	"sizeof without parenthesis is an abomination, and should never be used. ... The sane solution is: just add the f*cking parenthesis, and don't use the parsing oddity. ... And talking about ""prefix operators"" is a moronic thing to do. ... Think of it as a function, and get over your idiotic pissing match over how long you've both known C. That's irrelevant. ..."
0.664861085017581	"Absolutely. Anybody who does that is just terminally confused. ""return()"" is in no way a function. ... Here's an example of a really bad use of ""sizeof"" that doesn't have the parenthesis around the argument: sizeof(*p)->member. Quite frankly, if you do this, you should be shot. ... And let's face it: if you write your code so that it's easy to parse for a machine, and ignore how easy it is to parse for a human, I don't want you writing kernel code. ..."
0.781128159151678	"... However, please don't use the *INSANE* ARM ""v8"" naming. There must be something in the water in Cambridge, but the ARM ""version"" naming is just totally broken. ...maybe it all makes sense if you have drunk the ARM cool-aid and have joined the ARM cult, but to sane people and outsiders, it is just a f*cking mess. So - aarch64 is just another druggie name that the ARM people came up with after drinking too much of the spiked water in cambridge. ... - armv8 is totally idiotic and incomprehensible to anybody else...complete and utter nonsense. It's only confusing. Christ. Seriously. The insanity is so strong in the ARM version names that it burns. If it really makes sense to anybody ... you need to have your head examined. So please don't use ""aarch64"", because it's just f*cking crazy. And please don't use ""armv8"", because it's just completely retarded and confused."
0.82990870572725	"Guys, stop it now. Your ""problem"" isn't what any sane person cares about, and isn't what I started the RFC for. Seriously. NOBODY CARES. ... Stop whining."
0.490007805994375	Seriously. People who use BUG() statements like some kind of assert() are a menace to society. They kill machines.
0.65200348375345	And the commit seems to be pure shit. Why is it pure shit? Look at what users are left. THERE ARE NO USERS THAT SET THAT FIELD ANY MORE! ... I've pulled the changes for now, but I absolutely *detest* seeing things like this. ...
0.832673044601956	"Stop this ""we can break stuff"" crap. Who maintains udev? Regressions are not acceptable. I'm not going to change the kernel because udev broke, f*ck it. Seriously. More projects need to realize that regressions are totally and utterly unacceptable. ... That just encourages those package maintainers to be shit maintainers. ... And stop blaming the kernel for user space breakage!..."
0.808938865534043	This patch is insane. This is pure garbage. Anybody who thinks this: ... is a good idea should be shot. Don't do it. ...That's just f*cking insane. Stop this kind of idiocy. The code looks bad, and the logic is pure shit too.
0.803821124869647	... And it really is all stupidly and badly done. I bet we can make that code faster without really changing the  end result at all, just changing the algorithm. ... In fact, looking at select_idle_sibling(), I just want to puke. The thing is crazy. ... instead it does totally f*cking insane things ... The code is shit. Just fix the shit, instead of trying to come up with some totally different model. Ok? ...
0.800885794263853	"... I don't understand why this seems to be so hard for people to understand. ...this whole thread is a wonderful example of how F*CKING STUPID it was to even consider it. ... SO STOP DOING ABI CHANGES. WE DON'T DO THEM. ...but anybody who does it on purpose ""just because"" should not be involved in kernel development (or library development for that matter)."
0.784159544290281	"Stop this idiocy. ... The fact that you then continually try to make this a ""kernel issue"" is just disgusting. Talking about the kernel solving it ""properly"" is pretty dishonest, when the kernel wasn't the problem in the first place. "
0.752699207020063	"I also call bullshit on your ""it will surely be fixed when we know what's the right fix"" excuses. The fact is, you've spent the last several months blaming everybody but yourself, and actively told people to stop blaming you: ... despite having clearly seen the patch (you *replied* to it, for chissake, and I even told you in that same thread why that reply was wrong at the time). ... Kay, you are so full of sh*t that it's not funny. You're refusing to acknowledge your bugs, you refuse to fix them even when a patch is sent to you, and then you make excuses for the fact that we have to work around *your* bugs, and say that we should have done so from the very beginning. Yes, doing it in the kernel is ""more robust"". But don't play games, and stop the lying."
0.527212556614933	"David, I want to make it very clear that if you *ever* suggest another big include file cleanup, I will say ""f*ck no"" and block you from my emails forever. Ok? So don't bother. We're done with these kinds of games. Forever. It's not worth it, don't ever suggest it again for some other ""cleanup""."
0.561776485750964	That's just disgusting crazy talk. Christ, David, get a grip on yourself. ...
0.895154699659955	"Stop doing this f*cking crazy ad-hoc ""I have some other name available"" #defines. Use the same name, for chissake! Don't make up new random names. Just do ... to define the generic thing. Instead of having this INSANE ""two different names for the same f*cking thing"" crap. Stop it. Really. ...So NAK on this whole patch. It's bad. It's ugly, it's wrong, and it's actively buggy."
0.603324217832388	Did anybody ever actually look at this sh*t-for-brains patch? Yeah, I'm grumpy. But I'm wasting time looking at patches that have new code in them that is stupid and retarded. This is the VM, guys, we don't add stupid and retarded code. LOOK at the code, for chrissake. Just look at it. And if you don't see why the above is stupid and retarded, you damn well shouldn't be touching VM code.
0.75370965481074	"Rik, *LOOK* at the code like I asked you to, instead of making excuses for it. I'm not necessarily arguing with what the code tries to do. I'm arguing with the fact that the code is pure and utter *garbage*. It has two major (and I mean *MAJOR*) problems, both of which individually should make you ashamed for ever posting that piece of shit: The obvious-without-even-understanding-semantics problem: - it's humongously stupidly written. It calculates that 'flush_remote' flag WHETHER IT GETS USED OR NOT. Christ. I can kind of expect stuff like that in driver code etc, but in VM routines? Yes, the compiler may be smart enough to actually fix up the idiocy. That doesn't make it less stupid. The more-subtle-but-fundamental-problem: - regardless of how stupidly written it is on a very superficial level, it's even more stupid in a much more fundamental way. ... In other words, everything that was added by that patch is PURE AND UTTER SHIT. And THAT is what I'm objecting to. ... Because everything I see about ""flush_remote"" looks just wrong, wrong, wrong. And if there really is some reason for that whole flush_remote braindamage, then we have much bigger problems ... So that patch should be burned, and possibly used as an example of horribly crappy code for later generations. At no point should it be applied."
0.639439238563671	"But dammit, every single discussion I see, you use some *other* argument for it, like ""people don't have initrd"" or whatever crazy crap. That's what I was objecting to."
0.812937602367844	"Kees, you don't seem to understand. Breaking applications is unacceptable. End of story. It's broken them. Get over it. ... Your ""IT HAS TO BE DONE AT BOOT TIME, THE SKY IS FALLING, NOTHING ELSE IS ACCEPTABLE!"" ranting is a disease. Stop it."
0.772519803183371	We've been here before, haven't we? There's so much wrong with this that it's not funny. ... And I know you can do them, because you've done them in the past. So please don't continue to do the above.
0.711655666980764	"What part of ""We don't break user space"" do you have trouble understanding? ... End of discussion. I don't understand why people have such a hard time understanding such a simple concept. ... Seriously, IT IS THAT SIMPLE."
0.922058179089756	PLEASE NO! Dammit, why is this disease still so prevalent, and why do people continue to do this crap? __HAVE_ARCH_xyzzy is a f*cking retarded thing to do, and that's actually an insult to retarded people. ... The ... thing is a disease. ...
0.839837190743932	"Ingo, stop doing this kind of crap. ... You seem to be in total denial. ... Stop it. That kind of ""head-in-the-sand"" behavior is not conducive to good code, ... Seriously. If you can't make the non-THP case go faster, don't even bother sending out the patches. Similarly, if you cannot take performance results from others, don't even bother sending out the patches. ... So stop ignoring the feedback, and stop shooting the messenger. Look at the numbers, and admit that there is something that needs to be fixed."
0.735113006719663	"Ingo, stop it already! This is *exactly* the kind of ""blame everybody else than yourself"" behavior that I was talking about earlier. ... Ingo, look your code in the mirror some day, and ask yourself: why do you think this fixes a ""regression""? ...So by trying to make up for vsyscalls only in your numbers, you are basically trying to lie about regressions, and try to cover up the schednuma regression by fixing something else. ... See? That's bogus. When you now compare numbers, YOU ARE LYING. You have introduced a performance regression, and then trying to hide it by making something else go faster. ...The same is true of all your arguments about Mel's numbers wrt THP etc. Your arguments are misleading - either intentionally, of because you yourself didn't think things through. ..."
0.619279996973542	... Christ. That code is a mess. ...
0.609408807546925	"The games with ""max_block"" are hilarious. In a really sad way. That whole blkdev_get_blocks() function is pure and utter shit."
0.596965036693685	What a crock. That direct-IO code is hack-upon-hack. Whoever wrote it should be shot. ...
0.864831942365447	No. That patch is braindead. I wouldn't pull it even if it wasn't this late. ... What the f*ck is the point? ... What am I missing?
0.828360049974716	"Christ guys. This whole thread is retarded. The *ONLY* reason people seem to have for reverting that is a ""ooh, my feelings are hurt by how this was done, and now I'm a pissy bitch and I want to get this reverted"". Stop the f*cking around already. ... And if your little feelings got hurt, get your mommy to tuck you in, don't email me about it. Because I'm not exactly known for my deep emotional understanding and supportive personality, am I?"
0.771445396647378	"Ugh. This patch makes my eyes bleed. ... So I guess this patch fixes things, but it does make me go ""That's really *really* ugly""."
0.883628323990331	"Christ, I promised myself to not respond any more to this thread, but the insanity just continues, from people who damn well should know better. ... So stop these dishonest and disingenious arguments. They are full of crap. ... Every single argument I've heard of from the ""please revert"" camp has been inane. And they've been *transparently* inane, to the point where I don't understand how you can make them with a straght face and not be ashamed. ... Bullshit.... Anybody who claims that our ""process"" requires that things like that go on the mailing list and pass long reviews and discussions IS JUST LYING. ... Read the above arguments, and realise how shrill and outright STUPID that kind of ""we can now do anything without review"" argument is. ... You seem to seriously argue that it's a *bad* thing to put a note that one bit is already in use. That's f*cking moronic.... But that's not what the insane and pointless arguments in this thread have been. The whole thread has been just choch-full of pure STUPID. Please stop the inane and idiotic arguments already. The ""we must review every one-liner, and this destroys and makes a mockery of our review process"" argument in particular has been dishonest and pure crap...."
0.70051047765471	The reading comprehension here is abysmal. ...And none of that matters for my argument AT ALL.
0.812975256984369	"So please, just remove that idiotic ""if (!event->attr.exclude_guest)"" test. It's wrong. It cannot possibly do the right thing.  It is totally misdesigned, exactly because you don't even know beforehand if somebody uses virtualization or not."
0.654707615308268	Christ, why can't people learn?
0.954523604870709	"Ugh. This patch is just too ugly. Conditional locking like this is just too disgusting for words. ... I'm not applying disgusting hacks like this. ... No ""if (write) up_write() else up_read()"" crap. "
0.746910246289839	"Grr. This is still bullshit. Doing this: ... is fundamentally crap ... So doing *any* of these calculations in bytes is pure and utter crap. ... Anything that works in bytes is simply pure crap. And don't talk to me about 64-bit math and doing it in ""u64"" or ""loff_t"", that's just utterly moronic too. ... So the math is confused, the types are confused, and the naming is confused. Please, somebody check this out, because now *I* am confused. And btw, that whole commit happened too f*cking late too. ... I'm grumpy, because all of this code is UTTER SH*T, and it was sent to me. Why?"
0.668830425521625	"Christ, Mel. Your reasons in b22d127a39dd are weak as hell, and then you come up with *THIS* shit instead: ... Heck no. In fact, not a f*cking way in hell. Look yourself in the mirror, Mel. This patch is ugly, and *guaranteed* to result in subtle locking issues, and then you have the *gall* to quote the ""uhh, that's a bit ugly due to some trivial duplication"" thing in commit...  compared to the diseased abortion you just posted..."
0.861779097524422	"Mauro, SHUT THE FUCK UP! It's a bug alright - in the kernel. How long have you been a maintainer? And you *still* haven't learnt the first rule of kernel maintenance? ... Shut up, Mauro. And I don't _ever_ want to hear that kind of obvious garbage and idiocy from a kernel maintainer again. Seriously. ...The fact that you then try to make *excuses* for breaking user space, and blaming some external program that *used* to work, is just shameful. It's not how we work. Fix your f*cking ""compliance tool"", because it is obviously broken. And fix your approach to kernel programming"
0.816367403353986	"Yes, I'm upset. Very upset. ... So your question ""why would pulseaudio care"" is totally *irrelevant*, senseless, and has nothing to do with anything.1/2/2013 10:14:00"
0.852183325953959	Christ people. I already reported that it DOES NOT EVEN COMPILE. ... Alan apparently doesn't care about the patch he wrote to even bother fixing that, and the only person who does seem to care enough to carry two fixes around (Andrew) apparently doesn't feel that he's comfortable forwarding it to me ... I'm not picking up random patches from people who don't care enough about those patches to even bother fixing compile errors when reportyed and didn't even send them to me to begin with.
0.634416195361199	"Bullshit. That expectation is just a fact. ... We do not say ""user mode shouldn't"". Seriously. EVER. User mode *does*, and we deal with it. Learn it now, and stop ever saying that again. This is really starting to annoy me. Kernel developers who say ""user mode should be fixes to not do that"" should go somewhere else. "
0.858959804981735	"No way. ... In fact, just to prove how bad it is, YOU SCREWED IT UP YOURSELF. ... But the ""hacky workaround"" absolutely needs to be *automatic*. Because the ""driver writers need to get this subtle untestable thing right"" is *not* acceptable. That's the patch that Ming Lei did, and I refuse to have that kind of fragile crap in the kernel."
0.835011764104301	"No. You guys need to realize that I'm not talking crap like this this late. This is not major bugfixes. I already looked away once just because it's a new filesystem, but enough is enough. This is way way WAY too late to start sendign ""enhancements"". Seriously."
0.816305049876929	"No. Your pull requests are just illogical. I have yet to see a single reason why it should be merged. ... That's total bullshit. ... Again, total *bullshit*. ... ... Ingo, it's not us being silly, it is *you*. ... So here, let me state it very very clearly: I will not be merging kvmtool. ... In other words, I don't see *any* advantage to merging kvmtool. I think merging it would be an active mistake, and would just tie two projects together that just shouldn't be tied together. So nobody is ""hurting useful code"", except perhaps you. Explain to me why I'm wrong. I don't think you can. You certainly haven't so far."
0.583506575474461	NONE of your statements made any sense at all, since everything you talk about could have been done with a separate project. The only thing the lock-step does is to generate the kind of dependency that I ABSOLUTELY DETEST,
0.585813627833514	"You do realize that none of your arguments touched the ""why should Linus merge the tree"" question at all? Everything you said was about how it's more convenient for you and Ingo, not at all about why it should be better for anybody else. ... You're the only one working on it, so being convenient for you is the primary issue. Arguments like that actively make me not want to merge it, ..."
0.60181167503935	"Why? You've made this statement over and over and over again, and I've dismissed it over and over and over again because I simply don't think it's true. It's simply a statement with nothing to back it up. Why repeat it? THAT is my main contention. I told you why I think it's actually actively untrue. ... So you make these unsubstantiated claims about how much easier it is, and they make no sense. You never explain *why* it's so magically easier. ... Anyway, I'm done arguing. You can do what you want, but just stop misrepresenting it as being ""linux-next"" material unless you are willing to actually explain why it should be so."
0.674947029327941	"Ingo, stop this idiotic nonsense. You seem to think that ""kvmtool is useful for kernel"" is somehow relevant. IT IS TOTALLY IRRELEVANT."
0.543522330605922	Christ. This is so ugly that it's almost a work of art.
0.898171212539887	"Did anybody actually look at the code generation of this? Adding an external function call is *horrible*, ... Guys, the biggest cost of a function call is not the ""call"" instruction, it's all the crap around it ... And the excuse is ""so that we can add stuff to the wait loop"". What the f*ck? ... and which is something we have actively *avoided* in the past, because back-off is a f*cking idiotic thing, and the only real fix for contended spinlocks is to try to avoid the contention and fix the caller to do something smarter to begin with. In other words, the whole f*cking thing looks incredibly broken. At least give some good explanations for why crap like this is needed ..."
0.673548399428513	So you're potentially making things worse for just about everybody, in order to fix a problem that almost nobody can actually see. And apparently you don't even know the problem.. and as I already explained, THAT IS PURE AND UTTER BULLSHIT. It may make things WORSE. On all the things you haven't run to check that it does better. You just stated something that is not at all necessarily true. .... That's pure bullshit. ... And yet you go on to say that it will fix performance problems THAT WE DON'T EVEN KNOW ABOUT! After seeing *proof* to the exact contrary behavior! What f*cking planet are you from, again? Christ, that's hubris. ...
0.679866804765995	Christ, we should just try to get rid of the personality bits entirely, they are completely insane
0.687631886740125	Quite frankly, this is f*cking moronic.
0.768000665110527	Guys, this is not a dick-sucking contest. ... If Red Hat wants to deep-throat Microsoft, that's *your* issue.
0.878688755949116	"Quite frankly, I doubt that anybody will ever care, ... Plus quite frankly, signing random kernel vendor modules (indirectly) with a MS key is f*cking stupid to begin with. In other words, I really don't see why we should bend over backwards, when there really is no reason to. It's adding stupid code to the kernel only to encourage stupidities in other people. ... And the whole ""no, we only think it makes sense to trust MS keys"" argument is so f*cking stupid that if somebody really brings that up, I can only throw my hands up and say ""whatever"". In other words, none of this makes me think that we should do stupid things just to perpetuate the stupidity. "
0.905658073206459	Ugh. The placement of that #ifndef is just horrible, please don't do that.
0.617611993096367	Your arguments only make sense if you accept those insane assumptions to begin with. And I don't.
0.764044129341103	The softirq semantics are perfectly fine. Don't blame softirq for the fact that irq_exit() has had shit-for-brains for a long time. ... Don't blame the wrong code here.
0.844313808408253	Rafael, please don't *ever* write that crap again. ... Seriously. Why do I even have to mention this? Why do I have to explain this to somebody pretty much *every* f*cking merge window? This is not a new rule. ... So you should be well acquainted with the rule, and I'm surprised to hear that kind of utter garbage from you in particular. ...
0.724450098397838	"And you're happy shilling for a broken model? ... Your arguments constantly seem to miss that rather big point. You think this is about bending over when MS whispers sweet nothings in your ear.. ... You, on the other hand, seem to have drunk the cool-aid on the whole ""let's control the user"" crap. Did you forget what security was all about?"
0.647051420097368	"How f*cking hard is it for you to understand? Stop arguing about what MS wants. We do not care. We care bout the *user*. You are continually missing the whole point of security, and then you make some idiotic arguments about what MS wants you to do. It's irrelevant. The only thing that matters is what our *users* want us to do, and protecting *their* rights. As long as you seem to treat this as some kind of ""let's please MS, not our users"" issue, all your arguments are going to be crap."
0.625798160655577	"... Stop the fear mongering already. So here's what I would suggest, and it is based on REAL SECURITY and on PUTTING THE USER FIRST instead of your continual ""let's please microsoft by doing idiotic crap"" approach. ... Quite frankly, *you* are what he key-hating crazies were afraid of. You peddle the ""control, not security"" crap-ware. The whole ""MS owns your machine"" is *exactly* the wrong way to use keys."
0.72288842929421	This is the kind of totally bogus crap that no sane person should ever spout. Stop it.
0.838592740625719	I would love to blame gcc, but no, I think the code is crap. ... And gcc would be completely correct. That test is moronic.
0.630892693369288	Has Chris Ball been told what an incredible pain this kind of crap is, and that there's a damn good reason why WE DO NOT REBASE PUBLIC TREES THAT OTHERS MAY BE BASING THEIR DEVELOPMENT ON! Chris, can you hear me shouting? Don't do that.
0.814898612788688	Yeah, that would be a no. I finally got to look at the new architectures and be ready to pull them, and you just made sure I won't pull this. This is exactly the kind of crap I don't want to see in *any* pull requests, ... Why the f*ck are you doing back-merges? There is no excuse for even a single one. And here you have just about one back-merge per commit. No, no no.
0.746240823907864	No, guys. That cannot work. It's a completely moronic idea. 
0.658394270909275	Yeah, I'm a f*cking moron.
0.89429225368848	"Bullshit. This is a regression, and it needs to be fixed. The ""device needs power"" crap is just that - crap. Nobody cares. ... Claiming that we need to know the power regulator for an accelerometer is total utter idiocy and crap. ... The notion that you have to have regulator information in order to use some random device is insanity. I don't understand how you can even start to make excuses like that. It's so obviously bogus that it's not even funny. Why do I have to explain the ""no regressions"" to long-time kernel maintainers EVERY SINGLE RELEASE? What the f*ck is *wrong* with you people? Seriously?"
0.72609077025688	No it's not. ... which is entirely and utterly pointless. Christ, the amount of confusion in that tree.  ... Don't do this kind of thing. That branch is pointless, and just confused you.
0.448290342883974	Because you screwed up that pull request, and I argue that you screwed up exactly *because* it's ambiguous and confusing.
0.858225316657974	This is all *COMPLETELY* wrong. ... Fix ARC, don't try to blame generic code. You should have asked yourself why only ARC saw this bug, when the code apparently works fine for everybody else!
0.762227344574261	That's absolutely insane. It's insane for two reasons: - it's not SUFFICIENT. ... - it's POINTLESS and WRONG. ...
0.642801543359638	I'm a moron.
0.764311340776219	"Bullshit. That's exactly the wrong kind of thinking. ... This whole discussion has been f*cking moronic. The ""security"" arguments have been utter shite with clearly no thinking behind it, the feature is total crap ... and I'm seriously considering just getting rid of this idiotic dmesg_restrict thing entirely. Your comment is the very epitome of bad security thinking."
0.847415835636989	Why does this have the crappy cputime scaling overflow code, ... WTF happened here? I and others spent efforts so that we wouldn't need this kind of crap.
0.907571496503243	Ugh. Sorry, but this patch just looks stupid.
0.881317719791551	"F*ck yes it does. It means that NOBODY EVEN TEST-COMPILED THE TREE THAT GOT SENT TO ME. WTF? If that's not ""irresponsible and lame"", I don't know what the hell is."
0.857176751784924	And you are making that excuse exactly *why*? ... Stop making excuses for bad behavior. Just admit that you guys screwed up rather than trying to soldier on. ... That's a f*cking disgrace. ... Stop making excuses for it. Really. It just makes you look even worse. ...
0.841706410182745	This has so much wrong that I don't know where to start.
0.811682349964829	"Not pulled, because your hamster smells of eldeberries. This is not just bugfixes. In fact, as far as I can tell, this *introduces* bugs, ... I'm f*cking tired of people having problems understanding ""we're past rc5"". If it's not something you would call stable material, you shouldn't send it to me."
0.898389071886843	That patch is really ugly. And it doesn't make much sense. ... So the patch seems to make things just worse.
0.74514543967033	What the F*CK is wrong with people?
0.499798469578438	David, what the heck are you doing? ... Seriously. Those commits now have TOTALLY MISLEADING summary messages. ...
0.895006549813143	THIS IS SOME HORRIBLY BROKEN CRAP. ... Dammit, this has happened before, and it was broken then, and it is broken now. If they do, they are *F*CKING*BROKEN*. ... You need to start being more careful. ... There is no excuse for this. That commit is shit. ... And that totally crap commit is even marked for stable. I hate hate hate when this kind of crap happens. 
0.820733294099069	Grr. I hate it when people do this. Your merge message sucks.
0.594767694571466	"That's f*cking sad. You know *why* it's sad? ... Now, that should make you think about THE ABSOLUTE CRAP YOU MARK FOR -stable! ... Listen to yourself. In fact, there is a damn good solution"": don't mark crap for stable, and don't send crap to me after -rc4. ... Greg, the reason you get a lot of stable patches seems to be that you make it easy to act as a door-mat. ... You may need to learn to shout at people."
0.813954024912302	What the F*CK, guys? This piece-of-shit commit is marked for stable, but you clearly never even test-compiled it, did you? ...The declaration for gate_desc is very very different for 32-bit and 64-bit x86 for whatever braindamaged reasons. Seriously, WTF? I made the mistake of doing multiple merges back-to-back with the intention of not doing a full allmodconfig build in between them, and now I have to undo them all because this pull request was full of unbelievable shit. And why the hell was this marked for stable even *IF* it hadn't been complete and utter tripe? It even has a comment in the commit message about how this probably doesn't matter. So it's doubly crap: it's *wrong*, and it didn't actually fix anything to begin with. There aren't enough swear-words in the English language, so now I'll have to call you perkeleen vittupää just to express my disgust and frustration with this crap.
0.56989378938028	Ok. So your commit message and explanation was pure and utter tripe,
0.819841429399543	Ugh. I dislike this RCU'ism. It's bad code. It doesn't just look ugly and complex, it's also not even clever. It is possible that the compiler can fix up this horrible stuff and turn it into the nice clever stuff, but I dunno.
0.824927722167148	Please don't do these ugly and pointless preprocessor macro expanders that hide what the actual operation is. And this is really ugly. Again it's also then hidden behind the ugly macro. ...
0.698227424180082	"Yes it damn well is. Stop the f*cking stupid arguments, and instead listen to what I say. Here. Let me bold-face the most important part for you, so that you don't miss it in all the other crap: ... Nothing else. Seriously. Your ""you can't do it because we copy backwards"" arguments are pure and utter garbage, ... You're complicating the whole thing for no good reason. ..."
0.616728949463229	We should definitely drop it. The feature is an abomination. I thought gcc only allowed them at the end of structs, in the middle of a struct it's just f*cking insane beyond belief.
0.301180129969207	What drugs are you on? Your example is moronic, and against all _documented_ uses of chroot.
0.797550940052978	I can't even begin to say whether this is a good solution or not, because that if-conditional makes me want to go out and kill some homeless people to let my aggressions out. Can we please agree to *never* write code like this? Ever?
0.852199206638371	"The whole ""it's more convenient to use sleeping locks"" argument is PURE AND UTTER SHIT when it comes to really core code. ... Seriously. Your argument is bad, but more importantly, it is *dangerously* bad. It's crap that results in bad code: and the bad code is almost impossible to fix up later..."
0.701378112736595	So get your act together, and push back on the people you are supposed to manage. Because this is *not* acceptable for post-rc5, and I'm giving this single warning. Next time, I'll just ignore the sh*t you send me. Comprende?
0.856902684279614	Not acceptable. ... Plase stop sending me untested crap that doesn't even compile cleanly!
0.921042540209971	"Stop this idiotic ""blame gcc bug"" crap. Which part of my explanation for why it was *NOT* a compiler bug did you not understand? ... Stop the f*cking around already! The  whole ""we expect ww_ctx to be null"" thing shows that YOU DO NOT SEEM TO UNDERSTAND WHAT THE TEST ACTUALLY IS! ... Christ, can you really not understand that? NO NO NO NO. No a f*cking thousand times. It's not ""too broken in gcc"". It's too broken in the source code, and the fact that you don't even understand that is sad. You wrote the code, and you seem to be unable to admit that *your* code was buggy. It's not a compiler bug. It's your bug. Stand up like a man, instead of trying to flail around and blame anything else but yourself. So guys, get your act together, and stop blaming the compiler already."
0.74011502589211	This looks totally invalid....Your patch is horribly wrong.
0.923906284338418	"You need to also explain *why* people should apply it, and stop the f*cking idiotic arguing every time somebody comments about your patches.Stop this idiotic ""blame gcc bug"" crap. Which part of my explanation for why it was *NOT* a compiler bug did you not understand? ... Stop the f*cking around already! The  whole ""we expect ww_ctx to be null"" thing shows that YOU DO NOT SEEM TO UNDERSTAND WHAT THE TEST ACTUALLY IS! ... Christ, can you really not understand that? NO NO NO NO. No a f*cking thousand times. It's not ""too broken in gcc"". It's too broken in the source code, and the fact that you don't even understand that is sad. You wrote the code, and you seem to be unable to admit that *your* code was buggy. It's not a compiler bug. It's your bug. Stand up like a man, instead of trying to flail around and blame anything else but yourself. So guys, get your act together, and stop blaming the compiler already."
0.746996483533493	My point is that I have sixteen pointless messages in my mbox, half of which are due to just your argumentative nature.
0.748196495861618	This seems to be just pure stupid. ...Even the help message is pure and utter garbage ... Asking the user questions that make no f*cking sense to ask is stupid. And I'm not knowingly pulling stupid crap.
0.801111673168947	"Why? You're wrong. I mean, anybody who disagrees with me is pretty much wrong just on pure principles, but I actually mean a deeper kind of wrong than that. I mean a very objective ""you're clearly wrong"". ... .. and then you use a totally bogus example to try to ""prove"" your point. ... Your example is pure and utter shit, since you still get confused about what is actually const and what isn't. ... But that argument is BULLSHIT, because the fact is, the function *doesn't* do what you try to claim it does."
0.790756814333598	I think that code is bad, and you should feel bad.
0.690260971181633	Grr. I've pulled it, but looking at that history, it's just pure and utter f*cking garbage.
0.808209201906317	"No it's not. Thomas, stop this crap already. Look at the f*cking code carefully instead of just dismissing cases. ... So, Christ, Thomas, you have now *twice* dismissed a real concern with totally bogus ""that can never happen"" by explaining some totally unrelated *simple* case rather than the much more complex case. So please. Really. Truly look at the code and thing about it, or shut the f*ck up. No more of this shit where you glance at the code, find some simple case, and say ""that can't happen"", and dismiss the bug-report."
0.676094413400554	Ok, I'm sorry, but that's just pure bullshit then. ... This code is pure and utter garbage. It's beyond the pale how crazy it is.
0.772032774832641	No. I think it makes sense to put a big warning on any users you find, and fart in the general direction of any developer who did that broken pattern. Because code like that is obviously crap.
0.814078366045888	This looks completely broken to me. ... Wtf? Am I missing something?
0.746315757529654	Yeah, it's a hack, and it's wrong, and we should figure out how to do it right.
0.615374380008619	"Yes, yes, it may ""work"", but I'm not pulling that kind of hack just before a release....But dammit, using this kind of hackery, ... is just not acceptable."
0.821698890389565	The fact that it doesn't even compile makes me doubt your statement that it has been in linux-next. ... I fixed it up properly in the merge, but please try to figure out how the hell this passed through the cracks.
0.644268880722142	You messed up the pull request too.. The branch name is missing from that git line, even if you did mention it a few lines earlier...
0.589420664440607	"Adding Andrea to the Cc, because he's the author of that horridness. Putting Steven's test-case here as an attachement for Andrea, maybe that makes him go ""Ahh, yes, silly case"". Also added Kirill, because he was involved the last _PAGE_NUMA debacle."
0.811377426932941	It's misleading crap. Really. Just do a quick grep for that bit, and you see just *how* confused people are about it:...think about it. Just *THINK* about how broken that code is. The whole thing is a disaster. _PAGE_NUMA must die. It's shit.
0.801764456394772	This was obviously brought on by my frustration with the currently nasty do_notify_resume() always returning to iret for the task_work case, and PeterZ's patch that fixed that, but made the asm mess even *worse*.
0.558421257328433	But dammit, if you build with debug_info and then strip the end result, you're just insane. You made your build take ten times longer, use ten times more diskspace, and then you throw it all away. Crazy.
0.520737823507589	If most of the oopses you decode are on your own machine with your own kernel, you might want to try to learn to be more careful when writing code. And I'm not even kidding.
0.843447624873788	"Dammit, this is pure shit, and after having to deal with yet another pointless merge conflict due to stupid ""cleanups"" in Makefiles, IT DOES NOT EVEN COMPILE. And no, that's not due to a merge error of mine. It was that way in your tree. Hulk angry. Hulk smash. I fixed it up in the merge, but I shouldn't need to. This should have been caught in -next, and even if you compile for ARM as your primary target, I know *damn* well that no sane ARM developer actually compiles *on* ARM (because there are no machines where it's worth the pain), so you should make sure that the x86-64 build works too. If I can find compile errors within a couple of minutes of pulling and it's not a merge error of mine, the tree I'm pulling from is clearly crap. So I'm more than a bit grumpy. Get your act together, and don't send me any more shit. In fact, I would suggest you send nothing but obvious fixes from now on in this release. Because I won't be taking anything else."
0.889635217430461	"I don't think that works. That completely breaks randomize_stack_top(). So I'm not going to pull the parisc tree, this needs to be resolved sanely. In fact, I think that change to fs/exec.c is just completely broken:... and that ""+1"" just doesn't make sense, and fundamentally breaks STACK_RND_MASK. It also seems to be entirely pointless, ...So NAK on that whole fs/exec.c change. Afaik it's just wrong, and it's stupid."
0.630184621061049	"Oh, please, that's a British-level understatement. It's like calling WWII ""a small bother"". That's too ugly to live."
0.449750215987884	And that audit code really is aushit. I think I found a bug in it while just scanning it:
0.525431861535091	Grr. You missed the branch name. I can see from the SHA1 (and historical pull requests) that you meant the usual 'v4l_for_linus' branch, but please be more careful.
0.872563214072196	"I absolutely *detest* this patch....because the particular use in question is pure and utter garbage.... And btw, that horrid crap called ""kmap_to_page()"" needs to die too. When is it *ever* valid to use a kmap'ed page for IO? Here's a clue: never. I notice that we have a similar abortion in ""get_kernel_page[s]()"", which probably has the same broken source. We need to get *rid* of this crap, rather than add more of it. ... So who the f*ck sends static module data as IO? Just stop doing that. What's And that idiotic kmap_to_page() really needs to die too. Those *disgusting* get_kernel_page[s]() functions ... Mel, Rik, this needs to die. I'm sorry I didn't notice how crap it was earlier. ...Please let's just fix the real problem, don't add more horridness on top..."
0.72089149286705	"What BS is that? If you use an ""atomic_store_explicit()"", by definition you're either (a) f*cking insane (b) not doing sequential non-synchronizing code ... and a compiler that assumes that the programmer is insane may actually be correct more often than not, but it's still a shit compiler. Agreed? So I don't see how any sane person can say that speculative writes are ok. They are clearly not ok. Speculative stores are a bad idea in general. They are completely invalid for anything that says ""atomic"". This is not even worth discussing."
0.647358037294621	If you really think that, I hope to God that you have nothing to do with the C standard or any actual compiler I ever use. Because such a standard or compiler would be shit. It's sadly not too uncommon
0.709715222272489	"Is this whole thread still just for the crazy and pointless ""max_sane_readahead()""? Or is there some *real* reason we should care? Because if it really is just for max_sane_readahead(), then for the love of God, let us just do this ... and bury this whole idiotic thread."
0.891369005158643	"Quite frankly, I think it's stupid, and the ""documentation"" is not a benefit, it's just wrong.... I don't understand why you even argue this. Seriously, Paul, you seem to *want* to think that ""broken shit"" is acceptable, and that we should then add magic markers to say ""now you need to *not* be broken shit"".... Seriously, this whole discussion has been completely moronic. I don't understand why you even bring shit like this up... I mean, really? Anybody who writes code like that, or any compiler where that ""control_dependency()"" marker makes any difference what-so-ever for code generation should just be retroactively aborted. ... Seriously. This thread has devolved into some kind of ""just what kind of idiotic compiler cesspool crap could we accept"". Get away from that f*cking mindset. We don't accept *any* crap. Why are we still discussing this idiocy? It's irrelevant. ..."
0.875833025254089	No, please don't use this idiotic example. It is wrong....Anybody who argues anything else is wrong, or confused, or confusing.
0.596682372972141	Please, Debabrata, humor me, and just try the patch. And try reading the source code. Because your statement is BS.
0.853451341232159	...it's a pointless and wrong example....So your argument is *shit*. Why do you continue to argue it?...It's really not that complicated....Really, why is so hard to understand?
0.751115519708135	"This is why I don't like it when I see Torvald talk about ""proving"" things. It's bullshit."
0.834995657732345	"But your (and the current C standards) attempt to define this with some kind of syntactic dependency carrying chain will _inevitably_ get this wrong, and/or be too horribly complex to actually be useful. Seriously, don't do it. ... So just give it up. It's a fundamentally broken model. It's *wrong*, but even more importantly, it's not even *useful*, ...I really really really think you need to do this at a higher conceptual level, get away from all these idiotic ""these operations maintain the chain"" crap. "
0.863068900475542	"But that's *BS*. You didn't actually listen to the main issue. Paul, why do you insist on this carries-a-dependency crap? It's broken. ... The ""carries a dependency"" model is broken. Get over it.... I gave an alternate model (the ""restrict""), and you didn't seem to understand the really fundamental difference. ... So please stop arguing against that. Whenever you argue against that simple fact, you are arguing against sane compilers...."
0.783081336103737	"Whee. Third time is the charm. I didn't know my email address was *that* hard to type in correctly.Usually it's the ""torvalds"" that trips people up, but you had some issues with ""foundation"", didn't you ;)"
0.824876357783448	Oww, oww, oww. DAMMIT. ...So I'm pissed off. This patch was clearly never tested anywhere. Why was it sent to me?...Grr. Consider yourself cursed at. Saatana.
0.718306208013984	That's a technical issue, Stefani. ... And when Fengguang's automatic bug tester found the problem, YOU STARTED ARGUING WITH HIM.  Christ, well *excuuse* me for being fed up with this pointless discussion.
0.847522980596287	"Ugh. This is way late in the release, and the patch makes me go: ""This is completely insane"", which doesn't really help...This is just pure bullshit....So the above locking change is at least terminally stupid, and at most a sign of something much much worse.... there is no way in hell I will apply this obviously crap patch this late in the game. Because this patch is just inexcusable crap, and it should *not* have been sent to me in this state. ..."
0.728243886383727	Ugh. I pulled it, but things like this makes me want to dig my eyes out with a spoon:...
0.920455665209249	"So I think that adding ""visible"" to asmlinkage is actively wrong and misguided. And the compiler even told you so, but somebody then chose to ignore the compiler telling them that they did stupid things. Don't do crap like this."
0.831410984124405	Ugh. I absolutely detest this patch. If we're going to leave the TLB dirty, then dammit, leave it dirty. Don't play some half-way games....
0.796587186134485	"Why? This change looks completely and utterly bogus.... Guys, this is crap. ...  That's utter bullshit, guys. ...Exposing it at all is a disgrace. making it ""default y"" is doubly so. ... I'm not pulling crap like this. Get your act together. Why the heck should _I_ be the one that notices that this commit is insane and stupid? Yes, this is a pet peeve of mine. ... This cavalier attitude about asking people idiotic questions MUST STOP. Seriously. This is not some ""small harmless bug"". This mindset of crazy questions is a major issue!"
0.856699264079912	That's a cop-out. ... See? It's stupid. It's wrong. It's *bad*.
0.840723199202747	So I absolutely *hate* how this was done.... I'm pulling it this time, but quite frankly, next time I see this kind of ugly AND TOTALLY POINTLESS layering violation, I will just drop the stupid pull request. ... In other words, this was NOT OK. This was stupid and wrong, and violated all sanity. ... What the hell was going on here?
0.873308581453092	"And by ""their"" you mean Kay Sievers. Key, I'm f*cking tired of the fact that you don't fix problems in the code *you* write, so that the kernel then has to work around the problems you cause. Kay - one more time: you caused the problem, you need to fix it. None of this ""I can do whatever I want, others have to clean up after me"" crap."
0.855472379205654	It does become a problem when you have a system service developer who thinks the universe revolves around him, and nobody else matters, and people sending him bug-reports are annoyances that should be ignored rather than acknowledged and fixed. At that point, it's a problem. It looks like Greg has stepped in as a baby-sitter for Kay, and things are going to be fixed. And I'd really like to avoid adding hacky code to the kernel because of Kay's continued bad behavior, so I hope this works. But it's really sad that things like this get elevated to this kind of situation, and I personally find it annoying that it's always the same f*cking primadonna involved.
0.275204778054733	"Why are you making up these completely invalid arguments? Because you are making them up....And given this *fact*, your denial that ""PCI reboot should never be used"" is counterfactual. It may be true in some theoretical ""this is how the world should work"" universe, but in the real world it is just BS. Why are you so deep in denial about this?"
0.8424148553128	"NO I AM NOT! Dammit, this feature is f*cking brain-damaged. ...But even apart from the Xen case, it was just a confusing hell. Like Yoda said: ""Either they are the same or they are not. There is no 'try'"". So pick one solution. Don't try to pick the mixed-up half-way case that is a disaster and makes no sense."
0.844400180291415	"Ugh, so I pulled this, but I'm going to unpull it, because I dislike your new ""i_mmap_lastmap"" field.... makes me just gouge my eyes out. It's not only uglifying generic code, it's _stupid_ even when it's used....But the fact that it adds code to the generic file just adds insult to injury and makes me go ""no, I don't want to pull this""."
0.810241893708215	No it didn't. There was nothing accidental about it, and it doesn't even change it the way you claim.... Your explanation makes no sense for _another_ reason.... ... So tell us more about those actual problems, because your patch and explanation is clearly wrong. ... So this whole thing makes no sense what-so-ever.
0.65589567014732	and this, btw, is just another example of why MCE hardware designers are f*cking morons that should be given extensive education about birth control and how not to procreate.
0.613772109939011	BS. ...And you ignored the real issue: special-casing idle is *stupid*. It's more complicated, and gives fewer cases where it helps. It's simply fundamentally stupid and wrong.
0.613264482801719	It appears Intel is fixing their braindamage
0.649717217315903	Well, that's one way of reading that callchain. I think it's the *wrong* way of reading it, though. Almost dishonestly so.
0.802683443638446	Hmm. Less vomit-inducing, except for this part:...Ugh, that just *screams* for a helper function.
0.845755541606847	I did look at it, but the thing is horrible. I started on this something like ten times, and always ended up running away screaming.
0.758050886072245	.. so your whole argument is bogus, because it doesn't actually fix anything else.... You're not fixing the problem, you're fixing one unimportant detail that isn't worth fixing that way.
0.650790736595453	Greg, this is BS. ... so now you've re-introduced part of the problem, and marked it for stable too. The commit log shows nothing useful. ... And it really _isn't_ a good idea. ... Don't do this shit.
0.625397368137924	I'm ok with coding, I find your particular patch horrible. You add a dynamic allocator that will work *horribly* badly if people actually start using it for more complex cases, and then you use that for just about the least interesting case. And the way you do the dynamic allocator, nobody can ever allocate one of the wait-queue entries *efficiently* by just knowing that they are a leaf and there is never any recursive allocation....
0.904921625089633	"Why the heck are you making up ew and stupid event types? Now you make the generic VM code do stupid things like this:... which makes no sense at all. The names are some horrible abortion too (""RANDW""? That sounds like ""random write"" to me, not ""read-and-write"", which is commonly shortened RW or perhaps RDWR. Same foes for RONLY/WONLY - what kind of crazy names are those? But more importantly, afaik none of that is needed. Instead, tell us why you need particular flags, and don't make up crazy names like this. ...., so all those badly named states you've made up seem to be totally pointless. They add no actual information, but they *do* add crazy code like the above to generic code that doesn't even WANT any of this crap. ... So things like this need to be tightened up and made sane before any chance of merging it."
0.791872280599377	I really get the feeling that somebody needs to go over this patch-series with a fine comb to fix these kinds of ugly things
0.666816599355471	"I've pulled this, but I was pretty close to saying ""screw this shit"". Look at commit 9a630d15f16d, and pray tell me why those kinds of commit logs are excusable? That commit message is totally worthless noise. ... Seriously. ... That commit 9a630d15f16d is pure garbage. It's not the only crappy one, but it really does stand out. ...I'd really prefer it to talk about what it merges and why, but it's still *much* better than your completely information-free merge message."
0.83978135421398	If this comes from some man-page, then the man-page is just full of sh*t, and is being crazy. ...So NAK NAK NAK. This is insane and completely wrong. And the bugzilla is crazy too. Why would anybody think that readahead() is the same as read()?
0.907781850630657	I took it, but I think both your explanation and the patch itself is actually crap. It may fix the issue, but it's seriously confused. ... And the code is crap, because it uses ULONG_MAX etc in ways that simply make no f*cking sense. And why does it care about sizeof? ... So I think this fixes a problem, but it's all ugly as hell. ...It's not just that the code is unnecessarily complex, it's WRONG. ... It's just stupid and misleading, and it just so happens to work by random luck ...
0.814847994069666	".. and apparently this whole paragraph is completely bogus. It *does* break things, and for normal people. That's what the bug report is all about. So don't waffle about it.... Wrong. We don't break existing setups, and your attitude needs fixing. ... The problem needs to be solved some other way, and developers need to f*cking stop with the ""we can break peoples setups"" mentality./ Hans, seriously. You have the wrong mental model. Fix it."
0.638328554713879	Christoph, stop arguing. Trust me, Paul knows memory ordering. You clearly do *not*.
0.80932020852977	"Ok, so I'm looking at the code generation and your compiler is pure and utter *shit*. ... Lookie here, your compiler does some absolutely insane things with the spilling, including spilling a *constant*. For chrissake, that compiler shouldn't have been allowed to graduate from kindergarten. We're talking ""sloth that was dropped on the head as a baby"" level retardation levels here: ... Because it damn well is some seriously crazy shit. However, that constant spilling part just counts as ""too stupid to live"". ... ... This is your compiler creating completely broken code. "
0.670063503515984	I really dislike this one.... The other patches look sane, this one I really don't like. You may have good reasons for it, but it's disgusting.
0.756224095554717	"Tejun, absolutely nothing ""justifies"" things if they break. ...And if nothing breaks, you don't need the excuses. In other words, I'll happily pull this, but your excuses for it are wrong-headed. There is no ""crazyness justifies this"". That's crap. ... None of this ""the interface is crazy, so we can change it"".  Because that is pure and utter BS. Whether the interface is crazy or not is *entirely* irrelevant to whether it can be changed or not. The only thing that matters is whether people actually _trigger_ the issue you have in reality, not whether the issue is crazy."
0.821562254263407	Please don't. That thing is too ugly to exist. It also looks completely and utterly buggy. There's no way I'm taking it. If switch-names is suddenly conditional, what the f*ck happens to the name hash which is unconditionally done with a swap() right afterwards. There's no way that patch is correct
0.756083836600998	Why do you think it's not acceptable? Why do you raise a stink *one* day after the patch - that seems to not be very important - is sent out?... I don't think the patch is necessarily wrong, but I don't see why it would be critical, and I *definitely* don't see why the f*ck you are making a big deal of it. Go away, stop bothering people.
0.589344005635117	"See what my complaint is? Not this half-assery that used to be a small random detail, and that the patch makes into an institutionalized and explicit half-assery. (And Mikhail - I'm not ragging on you, even if I'm ragging on the patch. I understand why you did it the way you did, and it makes sense exactly in the ""let's reinstate old hackery"" model. I just think we can and should do better than that, now that the ""exchange"" vs ""move over"" semantics are so explicit)"
0.865007512161661	"That's just complete bullshit. The fact is, release() is not synchronous. End of story. ... Anybody who confuses the two is *wrong*. ... So please kill this ""FOPEN_SYNC_RELEASE"" thing with fire. It's crazy, it's wrong, it's stupid. It must die."
0.840164277449818	This is disgusting. Many (most?) __gup_fast() users just want a single page, and the stupid overhead of the multi-page version is already unnecessary. This just makes things much worse.
0.877953080315388	Yeah, this is pure crap. It doesn't even compile. ... Why the f*ck do you send me totally untested crap?
0.776721540812643	So adding the loop looks like just voodoo programming, not actually fixing anything.
0.866092865948806	Actually, the real fix would be to not be stupid, and just make the code do something like ...
0.854295716667847	"You're doing completelt faulty math, and you haven't thought it through. ...That's *insane*. It's crap. All just to try to avoid one page copy. Don't do it. ...Really, you need to rethink your whole ""zerocopy"" model. It's broken. Nobody sane cares. You've bought into a model that Sun already showed doesn't work. ..."
0.8323267749129	"No they aren't. You think they are, and then you find one case, and ignore all the others. ... So no, your patch doesn't change the fundamental issue in any way, shape, or form. I asked you to stop emailing me with these broken ""let's fix one special case, because I can't be bothered to understand the big picture"" patches. This was another one of those hacky sh*t patches that doesn't actually change the deeper issue. Stop it. Seriously. This idiotic thread has been going on for too long."
0.864786786184957	"No there isn't. Your ""action by the holder"" argument is pure and utter garbage, for a very simple and core reason: the *filesystem* doesn't know or care. ... ...Face it, your patch is broken. And it's *fundamentally* broken, which is why I'm so tired of your stupid ad-hoc hacks that cannot possibly work."
0.862510551029671	Yeah. Bloated, over-engineered, and stupid. ... Despite making the code slower, bigger, and buggier. I guess I'll fetch the git tree and see if they document this braindamage.. ...Oh well. What a cock-up. The code is insane in other ways too. ... I can't take it any more. That code is crazy.
0.743261689308738	"And no, we should *not* play games with ""tlb->local.next"". That just sounds completely and utterly insane. That's a hack, it's unclear, it's stupid, and it's connected to a totally irrelevant implementation detail, namely that random RCU freeing. Set a flag, for chrissake."
0.866057362276009	Improve the debugger, don't make kernel code worse because your out-of-tree debugging infrastructure is too broken to live.
0.862733574040647	"Ok, so things are somewhat calm, and I'm trying to take time off to see what's going on. And I'm not happy. ... Please don't call this thing a ""generic page table"". ... In other words, looking at this, I just go ""this is re-implementing existing models, and uses naming that is actively misleading"". I think it's actively horrible, in other words.  ... I also find it absolutely disgusting how you use USE_SPLIT_PTE_PTLOCKS for this, which seems to make absolutely zero sense. ... I'm also looking at the ""locking"". It's insane. It's wrong, and doesn't have any serialization. ... Rik, the fact that you acked this just makes all your other ack's be suspect. Did you do it just because it was from Red Hat, or do you do it because you like seeing Acked-by's with your name? ..."
0.560987991291822	WHAT? NONE OF WHAT YOU SAY MAKES ANY SENSE.
0.823936689346368	Umm. We had oopses showing it. Several times. ... .. and you and Andi repeatedly refused to make the code more robust when I asked. Which is why I don't work with Andi or you directly any more, ... Every time there were just excuses. Like now. ... I'm done with your crazy unwinder games. ... But this patch I NAK'ed because the code is not readable, and the infrastructure is not bearable. Live with it.
0.446516129557057	Andy, you need to lay off the drugs.
0.844176453836652	You have also marked 3.18-rc1 bad *twice*, along with the network merge, and the tty merge. That's just odd. But it doesn't make the bisect wrong, it just means that you fat-fingered thing and marked the same thing bad a couple of times. Nothing to worry about, unless it's a sign of early Parkinsons...
0.933474302722581	For a vmalloc() address, you'd have to actually walk the page tables. Which is a f*cking horrible idea. Don't do it. ... Where the hell does this crop up, and who does this insane thing anyway? It's wrong. 
0.845857540988828	"Ugh. That's horrid. Do we need to even support O_DIRECT in that case? ... In general, it's really a horrible thing to use, and tends to be a big red sign that ""somebody misdesigned this badly"""
0.901320343295736	Gaah. Why do you do this to me? ... That's the wrong format, but it's also the wrong branch name. ... EXCEPT THAT'S WRONG TOO! ... Please fix your script/workflow. I'm not pulling this mess.
0.838218598944263	".. why did that commit ever even get far enough to get to me? ... Either way, it shows a rather distinct lack of actual testing, wouldn't you say? I really see no excuse for crap like this. ...Linus ""not happy"" Torvalds"
0.609458734134122	I don't mind it if it's *one* line, and if people realize that the commentary in the commit in question was pure and utter shit. ... So really, I don't see the point of even a oneliner message. You guys know who the user is. There's no value in the message. Either you fix the user or you don't.
0.641800952909841	"No. Really. No. ... Thomas, you're in denial. ... Your argument ""it has a question mark in front of it"" objection is bogus. ... I'm just saying that your arguments to ignore CPU0 are pretty damn weak."
0.690940539586694	"So I'm not saying ""ifconfig is wonderful"". It's not. But I *am* saying that ""changing user interfaces and then expecting people to change is f*cking stupid"".... Because people who think that ""we'll just redesign everything"" are actually f*cking morons. Really. There's a real reason the kernel has the ""no regression"" policy. And that reason is that I'm not a moron."
0.867097200334674	"To quote the standard response for people who ignore regressions: ""SHUT THE FUCK UP""...I don't understand how people can't get this simple thing. You have two choices: - acknowledge and fix regressions - get the hell out of kernel development....Christ people. Why does this even have to be discussed any more?...But you guys need to shape up. We don't break things...."
0.854785435996622	"...End of discussion. Seriously. Your whinging about ""support costs"" is just crying over the fact that you have users. Deal with it. ...And dammit, I really never *ever* want to hear arguments against fixing regressions ever again. It really is the #1 rule for the kernel. There is *no* excuse for that NAK. There is only ""sorry""."
0.403539829518923	"Really. Shut up.... And if you aren't ok with ""wasting time"" on trying to give that kind of reassurances to users, then you shouldn't be working on the kernel. I'm serious about this. You really *need* to understand that. Your job as a kernel developer is very much to support the users. Not try to make it easy for *you* at the cost of being nasty for *them*."
0.875229035989576	"Yes, I actually would mind, unless you have a damn good reason for it....I really don't see why you should lie in your /proc/cpuinfo. ...Just give the real information. Don't lie. Quite frankly, the *only* actual real reason I've heard from you for not having the real bogomips there is ""waste of time"". And this whole thread has been *nothing* but waste of time. But it has been *you* wasting time, and that original commit. ... So quite frankly, my patience for you arguing ""wasting time"" is pretty damn low. I think your arguments are crap, I still think your NAK was *way* out of line, and I think it's completely *insane* to lie about bogomips. It's disasteful, it's dishonest, and there's no reason for it. ... Seriously, what kind of *insane* argument can you really marshal for lying to users?... Christ, this whole thing is annoying. I really find it *offensive* how you want to basically lie to users. Stop this idiocy. Really. There is no excuse."
0.848149330000619	"Fuck no. ... You are just making shit up. Bad shit. Get off the drugs, because it's not the good kind.... Cry me a river. ... Bullshit.  This whole thread is now marked as ""muted"" for me, because I can't take the BS any more. You make no sense. ...You're crazy. Go away. Or don't. I won't be seeing your emails anyway, so why would I care?"
0.864789437301234	Ugh.  This is too ugly, it needs to die.  ...   Because this is unreadable.
0.935150555016355	"Why do I say ""total crap""? ...it's really wrong. ...  The comment is also crap. ... So doing this in ""__may_sleep()"" is just bogus and horrible horrible crap. It turns the ""harmless ugliness"" into a real *harmful* bug. ...  PeterZ, please don't make ""debugging"" patches like this. Ever again. Because this was just stupid, and it took me too long to realize that despite the warning being shut up, the debug patch was still actively doing bad bad things."
0.859209414339482	"Ugh.  This patch is too ugly to live. ...  I really detest debug code (or compiler warnings) that encourage people to write code that is *worse* than the code that causes the debug code or warning to trigger. It's fundamentally wrong when those ""fixes"" actually make the code less readable and maintainable in the long run."
0.850665314373178	Because code like this is just crap:  ... really. It's just crazy.  It makes no sense. It's all just avoiding the warning, it's not making the code any better.
0.928193014452393	"This makes no sense.  You're trying to fix what you perceive as a problem in the page fault handling in some totally different place.  ... Don't try to make horrible code in insane places that have nothing to do with the fundamental problem. Why did you pick this particular get/put user anyway? There are tons others that we don't test, why did you happen pick these and then make it have that horrible and senseless error handling?  Because at *NO* point was it obvious that that patch had anything at all to do with ""out of memory"". Not in the code, not in your commit messages, *nowhere*.  ..."
0.585465349031012	Ugh. Your diffstat is crap, because you don't show the inexact renames that are very abundant in the nouveau driver.
0.844885819451751	"No. Really.  ... No. The whole concept of ""drop the lock in the middle"" is *BROKEN*. It's seriously crap. It's not just a bug, it's a really fundamentally wrong thing to do. ... No. That's still wrong. You can have two people holding a write-lock. Seriously. That's *shit*"
0.813210600320626	"No.  I pulled, and immediately unpulled again.  This is complete shit, and the compiler even tells you so:  ... I'm not taking ""cleanups"" like this. And I certainly don't appreciate being sent completely bogus shit pull requests at the end of the merge cycle."
0.886940810867813	"... There is absolutely no sane reason to use this crap, as far as I can tell. The new ""fs_inode_once()"" thing is just stupid. ...  Dammit, if we add wrapper and ""helper"" functions, they should *help*, not confuse. This thing is just badly named, and there is no actual real explanation for why it exists in the first place, nor for when to use one or the other. There is just an endless series of patches with pointless churn....  Explain it, or that crap gets undone.  I'm annoyed, because shit like this that comes in at the end of the merge window when everybody and their dog sends me random crap on the Friday afternoon before the merge window closes is just annoying as hell. ... Today has been a huge waste of time for me, and reading through this was just the last drop."
0.691796243178145	"And what *possible* situation could make that ""_once()"" version ever be valid? None. It's bogus. It's crap. It's insane. There is no way that it is *ever* a valid question to even ask."
0.91671094379576	"So my patch was obviously wrong, and I should feel bad for suggesting it. I'm a moron, and my expectations that ""pte_modify()"" would just take the accessed bit from the vm_page_prot field was stupid and wrong."
0.6122008243719	You make no sense. The commits you list were all on top of plain 4.0-rc2.
0.731148713868015	"NOOO!... Get rid of the f*cking size checks etc on READ_ONCE() and friends. ... Hell f*cking no. The ""something like so"" is huge and utter crap, because the barrier is on the wrong side."
0.880402513548066	Completely immaterial.  Seriously.  ... Answer: you don't. ... It's wrong. It's fundamentally invalid crap.  ... NO WAY IN HELL do we add generic support for doing shit. Really. If p9 does crazy crap, that is not an excuse to extend the crazy crap to more code.
0.812741561373601	Side note, you'll obviously also need to fix the actual bogus 'gp_init_delay' use in kernel/rcu/tree.c.  That code is horrible.
0.905712607701224	"Why not just revert that commit. It looks like garbage. ... The reason I think it's garbage is... code like the above is just crap to begin with.. So I don't think this code is ""fixable"". It really smells like a fundamental mistake to begin with. Just revert it, chalk it up as ""ok, that was a stupid idea"", and move on..."
0.802646459643388	Basically, I absolutely hate the notion of us doing something unsynchronized, when I can see us undoing a mmap that another thread is doing. It's wrong.  You also didn't react to all the *other* things that were wrong in that patch-set. The games you play with !fatal_signal_pending() etc are just crazy.  End result: I absolutely detest the whole thing. I told you what I consider an acceptable solution instead, that is much simpler and doesn't have any of the problems of your patchset.
0.733888913315611	Ok, I'm used to fixing up your whitespace and lack of capitalization, but you're getting so incoherent that I can no longer even parse it well enough to fix it up.  English *is* your first language, right? 
0.828849409027625	"Hell no.  Stop with the random BUG_ON() additions.  ... Dammit, there's no reason to add a BUG_ON() here in the first place, and the reason of ""but but it's an unused error return"": is f*cking retarded.  Stop this idiocy. We don't write crap code just to satisfy some random coding standard or shut up a compiler error.... NO NO NO. ... Really. I'm getting very tired indeed of people adding BUG_ON's like that. Stop it."
0.894670846543869	This is not at all equivalent, and it looks stupid.
0.591778298586291	Bullshit, Andrea.  That's *exactly* what you said in the commit message for the broken patch that I complained about. ... and I pointed out that your commit message was garbage, and that it's not at all as easy as you claim, and that your patch was broken, and your description was even more broken.... Your commit message was garbage, and actively misleading. Don't make excuses.
0.89851848599508	No. I refuse to touch this crap.... You really expect me to take crap like that? Hell no.  If your stuff isn't self-sufficient, then it's not something I want to ever pull. If the top of the tree you ask me to pull doesn't work (and quite frankly, every commit leading to it) then it's bad and unusable.  ...But it's one thing to have an unintentional bug, and another thing to do it on _purpose_.
0.730275869385983	No, it really isn't.  You still seem to be in denial:  ... NO YOU DID NOT! Stop claiming that.  You didn't actually test what you sent me. YOU TESTED SOMETHING ENTIRELY DIFFERENT.  Do you really not see the difference? Because that's a honking big difference. ...
0.848086212569989	"Ugh. I hate that. It looks bad, but it's also pointless.  ...Compilers that warn for the good kind of safe range tests should be taken out and shot. ...  so I just detest that buggy piece of crap for *so* many reasons.  It's also sad that a one-liner commit that claims to ""fix"" something was this broken to begin with. Grr. Honza, not good."
0.856048208225231	"What the hell have you done with the commit messages?  The first line is completely corrupted for those reverts, and as a result your own shortlog looks like crap and is completely misleading. ... presumably due to some horribly broken automation crap of yours that adds the ""[media]"" prefix or something.  How did you not notice this when you sent the shortlog? Or even earlier? This is some serious sh*t, since it basically means that your log messages are very misleading, since the one-liner actually implies exactly the reverse of what the commit does.  I unpulled this, because I think misleading commit messages is a serious problem, and basically *half* (and patch-wise, the bulk) of the commits in this queue are completely broken."
0.777722536063855	"... Christ, people. Learn C, instead of just stringing random characters together until it compiles (with warnings). ... There are arguments for them, but they are from weak minds. ... A later patch then added onto the pile of manure by adding *another* broken array argument, ...It's basically just lying about what is going on, and the only thing it documents is ""I don't know how to C"". ... Please people. ..."
0.853271502455323	"No. You think *WRONG*.  ... YOUR CODE IS WRONG, AND REALITY SHOWS THAT YOUR DEFAULT IS CRAP.  Really. ... BS.  The only reason for your interface was that it was simpler to use. You broke that.  And you broke that for no good reason. .... So your ""default"" is not actually safe. It breaks real cases, and doesn't add any security.  It's broken."
0.903699492799452	Your arguments all are entirely irrelevant to the fundamental issue.  And then when I suggest a *sane* interface that doesn't have this problem, your arguments are crap - again. ...  Bullshit. You clearly didn't even read my proposal. ...  Anyway, I'm not discussing this. You are clearly unwilling to just admit that your patch-series was broken, ... As such, why bother arguing? 
0.914618048499046	"No. Stop this theoretical idiocy.  We've tried it. I objected before people tried it, and it turns out that it was a horrible idea.... So this ""people should check for allocation failures"" is bullshit. It's a computer science myth. ... So no. ...Get over it. I refuse to go through that circus again. It's stupid. "
0.789953360471249	Really. Stop this idiocy. We have gone through this before. It's a disaster.
0.887251642052511	"Christ people. This is just sh*t.... But what makes me upset is that the crap is for completely bogus reasons. ...  and anybody who thinks that the above is  (a) legible (b) efficient (even with the magical compiler support) (c) particularly safe  is just incompetent and out to lunch.  The above code is sh*t, and it generates shit code. It looks bad, and there's no reason for it.... Really. Give me *one* reason why it was written in that idiotic way with two different conditionals, and a shiny new nonstandard function that wants particular compiler support to generate even half-way sane code, and even then generates worse code? A shiny function that we have never ever needed anywhere else, and that is just compiler-masturbation. ... So I really see no reason for this kind of complete idiotic crap. ... Because I'm not pulling this kind of completely insane stuff that generates conflicts at rc7 time, and that seems to have absolutely no reason for being anm idiotic unreadable mess. ... And it's a f*cking bad excuse for that braindamage.  I'm sorry, but we don't add idiotic new interfaces like this for idiotic new code like that. ...In fact, I want to make it clear to *everybody* that code like this is completely unacceptable. Anybody who thinks that code like this is ""safe"" and ""secure"" because it uses fancy overflow detection functions is so far out to lunch that it's not even funny. All this kind of crap does is to make the code a unreadable mess with code that no sane person will ever really understand what it actually does.  Get rid of it. And I don't *ever* want to see that shit again."
0.857769424321447	This code makes absolutely no sense.... So the code may end up *working*, but the comments in it are misleading, insane, and nonsensical. ...The comment is actively and entirely wrong. ... So the code looks insane to me. ...So in no case can that code make sense, as far as I can tell.
0.80220310251932	"Stop this idiocy. ... And that disgusting ""overflow_usub()"" in no way makes the code more readable. EVER.  So stop just making things up.... It wasn't more efficient, it wasn't more legible, and it simply had no excuse for it. Stop making excuses for shit."
0.719351104039322	"Really. That's it. Claiming that that is ""complicated"" and needs a helper function is not something sane people do. A fifth-grader that isn't good at math can understand that.  In contrast, nobody sane understands ""usub_overflow(a, b, &res)"".  So really. Stop making inane arguments."
0.629513685641965	"Hell no.... In exactly *WHAT* crazy universe does that make sense as an argument?  It's like saying ""I put literal shit on your plate, because there are potentially nutritious sausages that look superficially a bit like the dogshit I served you"".  Seriously.  ... It's *exactly* the same argument as ""dog poop superficially looks like good sausages"".  Is that really your argument?  There is never an excuse for ""usub_overflow()"". It's that simple.  No amount of _other_ overflow functions make that shit palatable. "
0.815783651625849	No.  Your repository is bogus.  I don't know what the hell you have done or why you have done it, but you have actually rebased *my* 4-3-rc7 commit that updates the Makefile from rc6 to rc7...  and there is no way I will take things like this.
0.850258143702855	Your arguments make no sense.  ... NO IT DOES NOT.  Christ, Paul. ...  You have turned it into something else in your mind. But your mind is WRONG.  ... I really don't understand your logic. ... That is NOT WHAT I WANT AT ALL.
0.801426469650129	"That's insane.  ... It is simply not sensible to have a ""wait_for_unlock()"" that then synchronizes loads or stores that happened *before* the wait. That's some crazy voodoo programming. ... Or just take the damn lock, and don't play any games at all."
0.486855775154713	Are we trying to win some obfuscated C contest here?
0.74723713946293	So this is definitely crap.  You can't return an error. ... Same deal. Returning an error is wrong.
0.716957130137101	"Absolutely not.  I will not take this, and it's stupid in the extreme.  ...That's just crazy talk.  ... So I don't know how many ways I can say ""NO"", but I'll not take anythign like this. It's *completely* wrong."
'''

if __name__ == '__main__':
	asyncio.run(main())
