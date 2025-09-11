import StatArbBot.Trading.pricesStarter
import StatArbBot.Trading.starterForCloudInstanceOfBot
import StatArbBot.Trading.paperStream

def main():
    print("booting up stat arb bot...")
    StatArbBot.Trading.pricesStarter.main()
    StatArbBot.Trading.starterForCloudInstanceOfBot.main()
    StatArbBot.Trading.paperStream.main()

if __name__ == "__main__":
    main()