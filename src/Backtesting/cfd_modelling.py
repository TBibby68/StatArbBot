from dataclasses import dataclass
import backtestConfig as config

# ignoring overnight financing for the intiial analysis
@dataclass
class CfdCosts:
    commission: float
    total_cost: float

def calculate_cfd_commission(
    quantity,
    commission_per_share,
    minimum_commission,
):
    return max(
        abs(quantity) * commission_per_share,
        minimum_commission,
    )

def calculate_cfd_costs(
    open_trade
):
    """
    Calculate CFD trading costs for a two-leg pairs trade.

    All annual rates should be decimals:
        0.05 = 5% per year

    Commission rates should also be decimals:
        0.001 = 10 bps
    """

    # ---------------------------------------------------------
    # Commission
    # Paid on BOTH entry and exit - based on price per share and a minimum value
    # ---------------------------------------------------------

    commission_1 = (
        calculate_cfd_commission(
            quantity=open_trade.position_size_1,
            commission_per_share=config.BacktestConfig.cfd_commission_per_share,
            minimum_commission=config.BacktestConfig.cfd_min_commission,
        )
        +
        calculate_cfd_commission(
            quantity=open_trade.position_size_1,
            commission_per_share=config.BacktestConfig.cfd_commission_per_share,
            minimum_commission=config.BacktestConfig.cfd_min_commission,
        )
    )

    commission_2 = (
        calculate_cfd_commission(
            quantity=open_trade.position_size_2,
            commission_per_share=config.BacktestConfig.cfd_commission_per_share,
            minimum_commission=config.BacktestConfig.cfd_min_commission,
        )
        +
        calculate_cfd_commission(
            quantity=open_trade.position_size_2,
            commission_per_share=config.BacktestConfig.cfd_commission_per_share,
            minimum_commission=config.BacktestConfig.cfd_min_commission,
        )
    )

    total_commission = (
        commission_1
        + commission_2
    )

    total_cost = (
        total_commission
    )

    return CfdCosts(
        commission=total_commission,
        total_cost=total_cost,
    )