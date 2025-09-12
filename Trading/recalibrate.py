import StatArbBot.Trading.pricesStarter
import StatArbBot.Trading.starterForCloudInstanceOfBot

def main():
    print("booting up stat arb bot...")
    StatArbBot.Trading.pricesStarter.main()
    StatArbBot.Trading.starterForCloudInstanceOfBot.main()

if __name__ == "__main__":
    main()

# this file runs just the starters, which we need to do every 2 weeks to test for updated cointegration