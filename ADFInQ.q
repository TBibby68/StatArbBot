/ my_script.q

/ create the columns: if you use ` then the elements will be symbols so you can't perform arithmetic on them!
/ Define a longer time series with 50 values
AAPL: 100 102 105 107 110 115 118 120 125 130 128 127 126 124 121 119 117 115 113 112 110 108 106 105 104 102 100 98 96 95 93 91 90 88 87 86 85 83 81 80 78 77 75 74 73 72 71 70 69 68
/show AAPL

/ Calculate difference and lag vectors
diff:AAPL - AAPL[1+til count AAPL] 
lagged:AAPL[1+til count AAPL]

/ remove the last value, a missing value: 0N from the vectors so we can run the regression without error. I think the vectors need to be longer?
diff: diff where not null diff
lagged: lagged where not null lagged

show diff
show lagged

/ run a basic linear regression on the 1st difference and the lagged vectors. 
.ml.online.sgd.linearRegression.fit[X;y;trend;paramDict]

/ what we want eventually is to assign a variable the result of the hypothesis test in this q script, and then pull that through in 
/ python so we can feed it into the rest of the trading bot. 