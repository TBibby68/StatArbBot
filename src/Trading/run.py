import StatArbBot.Trading.pricesStarter
import StatArbBot.Trading.starterForCloudInstanceOfBot
import StatArbBot.Trading.ibkrAPIEvents

def main():
    print("booting up stat arb bot...")
    StatArbBot.Trading.pricesStarter.main()
    StatArbBot.Trading.starterForCloudInstanceOfBot.main()
    StatArbBot.Trading.ibkrAPIEvents.main()

if __name__ == "__main__":
    main()

# this file runs the starts and then the actual bot