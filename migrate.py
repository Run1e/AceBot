import asyncio

import asyncpg

from config import DB_BIND

QUERIES = open("migrate.sql", "r").read()


def log(connection, message):
    print(message)


async def main():
    db = await asyncpg.connect(DB_BIND)
    db.add_log_listener(log)

    async with db.transaction():
        await db.execute(QUERIES)

        # populate facts if empty
        if await db.fetchval("SELECT COUNT(id) FROM facts") == 0:
            for fact in facts.strip().split("\n"):
                await db.execute("INSERT INTO facts (content) VALUES ($1)", fact)


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

if __name__ == "__main__":
    asyncio.run(main())
