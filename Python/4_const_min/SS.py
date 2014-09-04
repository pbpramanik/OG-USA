'''
------------------------------------------------------------------------
Last updated: 8/25/2014

Calculates steady state of OLG model with S age cohorts

This py-file calls the following other file(s):
            income.py
            demographics.py
            OUTPUT/given_params.pkl

This py-file creates the following other file(s):
    (make sure that an OUTPUT folder exists)
            OUTPUT/ss_vars.pkl
            OUTPUT/capital_dist_2D.png
            OUTPUT/capital_dist_3D.png
            OUTPUT/consumption_2D.png
            OUTPUT/consumption_3D.png
            OUTPUT/euler_errors_SS_2D.png
            OUTPUT/euler_errors_euler1_SS_3D.png
            OUTPUT/euler_errors_euler2_SS_3D.png
------------------------------------------------------------------------
'''

# Packages
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import time
import scipy.optimize as opt
import pickle
import income
import demographics


'''
------------------------------------------------------------------------
Imported user given values
------------------------------------------------------------------------
S            = number of periods an individual lives
J            = number of different ability groups
T            = number of time periods until steady state is reached
starting_age = age of first members of cohort
beta         = discount factor
sigma        = coefficient of relative risk aversion
alpha        = capital share of income
nu           = contraction parameter in steady state iteration process
               representing the weight on the new distribution gamma_new
A            = total factor productivity parameter in firms' production
               function
delta        = depreciation rate of capital
ctilde       = minimum value amount of consumption
ltilde       = measure of time each individual is endowed with each
               period
chi          = discount factor
eta          = Frisch elasticity of labor supply
T            = number of periods until the steady state
TPImaxiter   = Maximum number of iterations that TPI will undergo
TPImindist   = Cut-off distance between iterations for TPI
------------------------------------------------------------------------
'''

variables = pickle.load(open("OUTPUT/given_params.pkl", "r"))
for key in variables:
    globals()[key] = variables[key]

'''
------------------------------------------------------------------------
Generate income and demographic parameters
------------------------------------------------------------------------
e            = S x J matrix of age dependent possible working abilities
               e_s
omega        = T x S x J array of demographics
g_n          = steady state population growth rate
omega_SS     = steady state population distribution
children     = T x starting_age x J array of children demographics
surv_rate    = S x 1 array of survival rates
mort_rate    = S x 1 array of mortality rates
------------------------------------------------------------------------
'''

print 'Generating income distribution.'
e = income.get_e(S, J, starting_age, ending_age, bin_weights)
print '\tFinished.'
print 'Generating demographics.'
omega, g_n, omega_SS, children, surv_rate = demographics.get_omega(
    S, J, T, bin_weights, starting_age, ending_age, E)
mort_rate = 1-surv_rate
retire = np.round(7.0 * S / 16.0)
chi_n_multiplier = 1.0
# This is how to do it, but need to generalize TPI version
# chi_n[retire:] = (chi_n_multiplier*mort_rate[retire:] + 1 - chi_n_multiplier*mort_rate[retire])

# chi_n = (chi_n_multiplier*mort_rate + 1)
# chi_n[-1] = chi_n[-2]
# later = np.round(12.0 * S / 16.0)
# exp = np.linspace(1, 9, 20)
# chi_n[later:] = chi_n[later:] ** exp - chi_n[later] ** exp + chi_n[later]
# chi_n[retire:] *= (1.0 + mort_rate[retire:]-mort_rate[retire])**10.0
# chi_n[retire:] = (np.arange(S-retire)+2.0)**2.0
surv_rate[-1] = 0.0
mort_rate[-1] = 1
cum_surv_rate = np.empty(S)
for s in xrange(S):
    cum_surv_rate[s] = np.prod(surv_rate[:s])
cum_mort_rate = 1.0 - cum_surv_rate
print '\tFinished.'

print 'The following are the parameter values of the simulation:'
print '\tS:\t\t\t\t', S
print '\tJ:\t\t\t\t', J
print '\tT:\t\t\t\t', T
print '\tStarting Age:\t', starting_age
print '\tbeta:\t\t\t', beta
print '\tsigma:\t\t\t', sigma
print '\talpha:\t\t\t', alpha
print '\tnu:\t\t\t\t', nu
print '\tA:\t\t\t\t', A
print '\tdelta:\t\t\t', delta
print '\tl-tilde:\t\t', ltilde
print '\tchi_n:\t\t\tSee graph'
print '\tchi_b:\t\t\t', chi_b
print '\teta:\t\t\t', eta
print '\tg_n:\t\t\t', g_n
print '\tg_y:\t\t\t', g_y

'''
------------------------------------------------------------------------
Finding the Steady State
------------------------------------------------------------------------
K_guess_init = (S-1 x J) array for the initial guess of the distribution
               of capital
L_guess_init = (S x J) array for the initial guess of the distribution
               of labor
solutions    = ((S * (S-1) * J * J) x 1) array of solutions of the
               steady state distributions of capital and labor
Kssmat       = ((S-1) x J) array of the steady state distribution of
               capital
Kssmat2      = SxJ array of capital (zeros appended at the end of
               Kssmat2)
Kssmat3      = SxJ array of capital (zeros appended at the beginning of
               Kssmat)
Kssvec       = ((S-1) x 1) vector of the steady state level of capital
               (averaged across ability types)
Kss          = steady state aggregate capital stock
K_agg        = Aggregate level of capital
Lssmat       = (S x J) array of the steady state distribution of labor
Lssvec       = (S x 1) vector of the steady state level of labor
               (averaged across ability types)
Lss          = steady state aggregate labor
Yss          = steady state aggregate output
wss          = steady state real wage
rss          = steady state real rental rate
cssmat       = SxJ array of consumption across age and ability groups
runtime      = Time needed to find the steady state (seconds)
hours        = Hours needed to find the steady state
minutes      = Minutes needed to find the steady state, less the number
               of hours
seconds      = Seconds needed to find the steady state, less the number
               of hours and minutes
------------------------------------------------------------------------
'''

# Functions and Definitions


def get_Y(K_now, L_now):
    '''
    Parameters: Aggregate capital, Aggregate labor

    Returns:    Aggregate output
    '''
    Y_now = A * (K_now ** alpha) * ((L_now) ** (1 - alpha))
    return Y_now


def get_w(Y_now, L_now):
    '''
    Parameters: Aggregate output, Aggregate labor

    Returns:    Returns to labor
    '''
    w_now = (1 - alpha) * Y_now / L_now
    return w_now


def get_r(Y_now, K_now):
    '''
    Parameters: Aggregate output, Aggregate capital

    Returns:    Returns to capital
    '''
    r_now = (alpha * Y_now / K_now) - delta
    return r_now


def get_L(e, n):
    '''
    Parameters: e, n

    Returns:    Aggregate labor
    '''
    L_now = np.sum(e * omega_SS * n)
    return L_now


def MUc(c):
    '''
    Parameters: Consumption

    Returns:    Marginal Utility of Consumption
    '''
    output = c**(-sigma)
    return output


def MUl(n):
    '''
    Parameters: Labor

    Returns:    Marginal Utility of Labor
    '''
    output = - chi_n.reshape(S, 1) * ((ltilde-n) ** (-eta))
    return output


def MUb(bq):
    '''
    Parameters: Intentional bequests

    Returns:    Marginal Utility of Bequest
    '''
    output = chi_b * (bq ** (-sigma))
    return output


def Euler1(w, r, e, L_guess, K1, K2, K3, B):
    '''
    Parameters:
        w        = wage rate (scalar)
        r        = rental rate (scalar)
        e        = distribution of abilities (SxJ array)
        L_guess  = distribution of labor (SxJ array)
        K1       = distribution of capital in period t ((S-1) x J array)
        K2       = distribution of capital in period t+1 ((S-1) x J array)
        K3       = distribution of capital in period t+2 ((S-1) x J array)

    Returns:
        Value of Euler error.
    '''
    euler = MUc((1 + r)*K1 + w * e[:-1, :] * L_guess[:-1, :] + B.reshape(1, J) / bin_weights - K2 * np.exp(
        g_y)) - beta * surv_rate[:-1].reshape(S-1, 1) * (
        1 + r)*MUc((1 + r)*K2 + w * e[1:, :] * L_guess[1:, :] + B.reshape(1, J) / bin_weights - K3 * np.exp(
            g_y)) * np.exp(-sigma * g_y)
    return euler


def Euler2(w, r, e, L_guess, K1_2, K2_2, B):
    '''
    Parameters:
        w        = wage rate (scalar)
        r        = rental rate (scalar)
        e        = distribution of abilities (SxJ array)
        L_guess  = distribution of labor (SxJ array)
        K1_2     = distribution of capital in period t (S x J array)
        K2_2     = distribution of capital in period t+1 (S x J array)

    Returns:
        Value of Euler error.
    '''
    euler = MUc((1 + r)*K1_2 + w * e * L_guess + B.reshape(1, J) / bin_weights - K2_2 * 
        np.exp(g_y)) * w * e + MUl(L_guess)
    return euler


def Euler3(w, r, e, L_guess, K_guess, B):
    euler = MUc((1 + r)*K_guess[-2, :] + w * e[-1, :] * L_guess[-1, :] + B.reshape(1, J) / bin_weights - K_guess[-1, :] * 
        np.exp(g_y)) - np.exp(-sigma * g_y) * MUb(K_guess[-1, :])
    return euler


def Steady_State(guesses):
    '''
    Parameters: Steady state distribution of capital guess as array
                size S-1

    Returns:    Array of S-1 Euler equation errors
    '''
    K_guess = guesses[0: S * J].reshape((S, J))
    B = (K_guess * omega_SS * mort_rate.reshape(S, 1)).sum(0)
    K = (omega_SS * K_guess).sum()
    L_guess = guesses[S * J:].reshape((S, J))
    # L_guess_init[retire:] = np.ones((S-retire, J)) * 0.1
    # for j in xrange(J):
    #     L_guess_init[retire-5:retire, j] = np.linspace(L_guess_init[retire-5, j], 0.1, 5)

    L = get_L(e, L_guess)
    Y = get_Y(K, L)
    w = get_w(Y, L)
    r = get_r(Y, K)
    BQ = (1 + r) * B
    K1 = np.array(list(np.zeros(J).reshape(1, J)) + list(K_guess[:-2, :]))
    K2 = K_guess[:-1, :]
    K3 = K_guess[1:, :]
    K1_2 = np.array(list(np.zeros(J).reshape(1, J)) + list(K_guess[:-1, :]))
    K2_2 = K_guess
    error1 = Euler1(w, r, e, L_guess, K1, K2, K3, BQ)
    error2 = Euler2(w, r, e, L_guess, K1_2, K2_2, BQ)
    error3 = Euler3(w, r, e, L_guess, K_guess, BQ)
    # Check and punish constraing violations
    mask1 = L_guess < 0
    error2[mask1] += 1e9
    mask2 = L_guess > ltilde
    error2[mask2] += 1e9
    if K_guess.sum() <= 0:
        error1 += 1e9
    cons = (1 + r) * K1_2 + w * e * L_guess + BQ.reshape(1, J) / bin_weights - K2_2 * np.exp(g_y)
    mask3 = cons < 0
    error2[mask3] += 1e9
    # mask4 = np.diff(L_guess) > 0
    # error2[mask4] += 1e9
    return list(error1.flatten()) + list(error2.flatten()) + list(error3.flatten())


def consumption(b_guess, n_guess, BQ, r, w):

    b1 = np.array(list(np.zeros(J).reshape(1, J)) + list(b_guess[:-1]))
    b2 = b_guess
    consumption = (1+r) * b1 + e * w * n - np.exp(g_y) * b2 

    return consumption


def Period_Utility(b_guess, n_guess, BQ, r, w):

    utility = np.empty((S,J))
    utility[:-1, :] = ( (consumption(b_guess, n_guess, BQ, r, w)[:-1]**(1-sigma) - 1)/(1-sigma) ) + \
        chi_n * ( ((l_tilde - n_guess[:-1])**(1 - eta)) / (1 - eta) )
    utility[-1, :] = ( (consumption(b_guess, n_guess, BQ, r, w)[-1]**(1-sigma) - 1)/(1-sigma) ) + \
        chi_n * ( ((l_tilde - n_guess[:-1])**(1 - eta)) / (1 - eta) ) + \
        chi_b * np.exp(g_y * (1-sigma)) * ( (b_guess[-1]**(1-sigma)) / (1-sigma) )

    return utility


def Lifetime_Utility(guesses):

    b_guess = guesses[: S*J].reshape(S, J)
    n_guess = guesses[S*J: ].reshape(S, J)

    K = (omega_SS * b_guess).sum()
    L = (omega_SS * n_guess).sum()
    BQ = (mort_rate * omega_SS * b_guess).sum(0)
    Y = get_Y(K, L)
    r = get_r(Y, K)
    w = get_w(Y, L)

    utility = ( beta**(np.arange(S)+1.0) * cum_surv_rate * \
            np.exp(g_y * (np.np.arange(S)+1.0) * (1.0-sigma)) * \
            Period_Utility(b_guess, n_guess, BQ, r, w) ).sum()

    return -utility


def borrowing_constraints(K_dist, w, r, e, n, BQ):
    '''
    Parameters:
        K_dist = Distribution of capital ((S-1)xJ array)
        w      = wage rate (scalar)
        r      = rental rate (scalar)
        e      = distribution of abilities (SxJ array)
        n      = distribution of labor (SxJ array)

    Returns:
        False value if all the borrowing constraints are met, True
            if there are violations.
    '''
    b_min = np.zeros((S-1, J))
    b_min[-1, :] = (ctilde + bqtilde - w * e[S-1, :] * ltilde - BQ.reshape(1, J) / bin_weights) / (1 + r)
    for i in xrange(S-2):
        b_min[-(i+2), :] = (ctilde + np.exp(g_y) * b_min[-(i+1), :] - w * e[
            -(i+2), :] * ltilde - BQ.reshape(1, J) / bin_weights) / (1 + r)
    difference = K_dist - b_min
    if (difference < 0).any():
        return True
    else:
        return False


def constraint_checker(Kssmat, Lssmat, wss, rss, e, cssmat, BQ):
    '''
    Parameters:
        Kssmat = steady state distribution of capital ((S-1)xJ array)
        Lssmat = steady state distribution of labor (SxJ array)
        wss    = steady state wage rate (scalar)
        rss    = steady state rental rate (scalar)
        e      = distribution of abilities (SxJ array)
        cssmat = steady state distribution of consumption (SxJ array)

    Created Variables:
        flag1 = False if all borrowing constraints are met, true
               otherwise.
        flag2 = False if all labor constraints are met, true otherwise

    Returns:
        Prints warnings for violations of capital, labor, and
            consumption constraints.
    '''
    print 'Checking constraints on capital, labor, and consumption.'
    flag1 = False
    if Kssmat.sum() <= 0:
        print '\tWARNING: Aggregate capital is less than or equal to zero.'
        flag1 = True
    if borrowing_constraints(Kssmat, wss, rss, e, Lssmat, BQ) is True:
        print '\tWARNING: Borrowing constraints have been violated.'
        flag1 = True
    if flag1 is False:
        print '\tThere were no violations of the borrowing constraints.'
    flag2 = False
    if (Lssmat < 0).any():
        print '\tWARNING: Labor supply violates nonnegativity constraints.'
        flag2 = True
    if (Lssmat > ltilde).any():
        print '\tWARNING: Labor suppy violates the ltilde constraint.'
    if flag2 is False:
        print '\tThere were no violations of the constraints on labor supply.'
    if (cssmat < 0).any():
        print '\tWARNING: Conusmption volates nonnegativity constraints.'
    else:
        print '\tThere were no violations of the constraints on consumption.'

starttime = time.time()

K_guess_init = np.ones((S, J)) * .05
L_guess_init = np.ones((S, J)) * .95
# L_guess_init[retire:] = np.ones((S-retire, J)) * 0.1
guesses = list(K_guess_init.flatten()) + list(L_guess_init.flatten())

print 'Solving for steady state level distribution of capital and labor.'
solutions = opt.fsolve(Steady_State, guesses, xtol=1e-9, col_deriv=1)
print '\tFinished.'

runtime = time.time() - starttime
hours = runtime / 3600
minutes = (runtime / 60) % 60
seconds = runtime % 60
print 'Finding the steady state took %.0f hours, %.0f minutes, and %.0f \
seconds.' % (abs(hours - .5), abs(minutes - .5), seconds)

Kssmat = solutions[0:(S-1) * J].reshape(S-1, J)
BQ = solutions[(S-1)*J:S*J]
Bss = (np.array(list(Kssmat) + list(BQ.reshape(1, J))).reshape(S, J) * omega_SS * mort_rate.reshape(S, 1)).sum(0)
Kssmat2 = np.array(list(np.zeros(J).reshape(1, J)) + list(Kssmat))
Kssmat3 = np.array(list(Kssmat) + list(BQ.reshape(1, J)))

Kssvec = Kssmat.sum(1)
Kss = (omega_SS[:-1, :] * Kssmat).sum() + (omega_SS[-1,:]*BQ).sum()
Kssavg = Kssvec.mean()
Kssvec = np.array([0]+list(Kssvec))
Lssmat = solutions[S * J:].reshape(S, J)
Lssvec = Lssmat.sum(1)
Lss = get_L(e, Lssmat)
Lssavg = Lssvec.mean()
Yss = get_Y(Kss, Lss)
wss = get_w(Yss, Lss)
rss = get_r(Yss, Kss)

cssmat = (1 + rss) * Kssmat2 + wss * e * Lssmat + (1 + rss) * Bss.reshape(1, J)/bin_weights.reshape(1,J) - np.exp(g_y) * Kssmat3


constraint_checker(Kssmat, Lssmat, wss, rss, e, cssmat, BQ)

print 'The steady state values for:'
print "\tCapital:\t\t", Kss
print "\tLabor:\t\t\t", Lss
print "\tOutput:\t\t\t", Yss
print "\tWage:\t\t\t", wss
print "\tRental Rate:\t", rss
print "\tBequest:\t\t", Bss.sum()

'''
------------------------------------------------------------------------
Graph of Chi_n
------------------------------------------------------------------------
'''

plt.figure()
plt.plot(np.arange(S)+21, chi_n)
plt.xlabel(r'Age cohort - $s$')
plt.ylabel(r'$\chi _n$')
plt.savefig('OUTPUT/chi_n')

'''
------------------------------------------------------------------------
 Generate graphs of the steady-state distribution of wealth
------------------------------------------------------------------------
domain     = 1 x S vector of each age cohort
------------------------------------------------------------------------
'''

print 'Generating steady state graphs.'
domain = np.linspace(starting_age, ending_age, S)
Jgrid = np.zeros(J)
for j in xrange(J):
    Jgrid[j:] += bin_weights[j]

# 2D Graph
plt.figure()
plt.plot(domain, Kssvec, color='b', linewidth=2, label='Average capital stock')
plt.axhline(y=Kssavg, color='r', label='Steady state capital stock')
plt.title('Steady-state Distribution of Capital')
plt.legend(loc=0)
plt.xlabel(r'Age Cohorts $S$')
plt.ylabel('Capital')
plt.savefig("OUTPUT/capital_dist_2D")

# 3D Graph
cmap1 = matplotlib.cm.get_cmap('summer')
cmap2 = matplotlib.cm.get_cmap('jet')
# Jgrid = np.linspace(1, J, J)
X, Y = np.meshgrid(domain, Jgrid)
fig5 = plt.figure()
ax5 = fig5.gca(projection='3d')
ax5.set_xlabel(r'age-$s$')
ax5.set_ylabel(r'ability-$j$')
ax5.set_zlabel(r'individual savings $\bar{b}_{j,s}$')
# ax5.set_title(r'Steady State Distribution of Capital Stock $K$')
ax5.plot_surface(X, Y, Kssmat2.T, rstride=1, cstride=1, cmap=cmap2)
plt.savefig('OUTPUT/capital_dist_3D')

'''
------------------------------------------------------------------------
 Generate graph of the steady-state distribution of intentional bequests
------------------------------------------------------------------------
'''

plt.figure()
plt.plot(np.arange(J)+1, BQ)
plt.xlabel(r'ability-$j$')
plt.ylabel(r'bequests $\overline{bq}_{j,E+S+1}$')
plt.savefig('OUTPUT/intentional_bequests')

'''
------------------------------------------------------------------------
 Generate graphs of the steady-state distribution of labor
------------------------------------------------------------------------
'''

# 2D Graph
plt.figure()
plt.plot(domain, Lssvec, color='b', linewidth=2, label='Average Labor Supply')
plt.axhline(y=Lssavg, color='r', label='Steady state labor supply')
plt.title('Steady-state Distribution of Labor')
plt.legend(loc=0)
plt.xlabel(r'Age Cohorts $S$')
plt.ylabel('Labor')
plt.savefig("OUTPUT/labor_dist_2D")

# 3D Graph
fig4 = plt.figure()
ax4 = fig4.gca(projection='3d')
ax4.set_xlabel(r'age-$s$')
ax4.set_ylabel(r'ability-$j$')
ax4.set_zlabel(r'individual labor supply $\bar{l}_{j,s}$')
# ax4.set_title(r'Steady State Distribution of Labor Supply $K$')
ax4.plot_surface(X, Y, (Lssmat).T, rstride=1, cstride=1, cmap=cmap1)
plt.savefig('OUTPUT/labor_dist_3D')

'''
------------------------------------------------------------------------
Generate graph of Consumption
------------------------------------------------------------------------
'''

# 2D Graph
plt.figure()
plt.plot(domain, cssmat.mean(1), label='Consumption')
plt.title('Consumption across cohorts: S = {}'.format(S))
# plt.legend(loc=0)
plt.xlabel('Age cohorts')
plt.ylabel('Consumption')
plt.savefig("OUTPUT/consumption_2D")

# 3D Graph
fig9 = plt.figure()
ax9 = fig9.gca(projection='3d')
ax9.plot_surface(X, Y, cssmat.T, rstride=1, cstride=1, cmap=cmap2)
ax9.set_xlabel(r'age-$s$')
ax9.set_ylabel(r'ability-$j$')
ax9.set_zlabel('Consumption')
ax9.set_title('Steady State Distribution of Consumption')
plt.savefig('OUTPUT/consumption_3D')

'''
------------------------------------------------------------------------
Check Euler Equations
------------------------------------------------------------------------
k1          = (S-1)xJ array of Kssmat in period t-1
k2          = copy of Kssmat
k3          = (S-1)xJ array of Kssmat in period t+1
k1_2        = SxJ array of Kssmat in period t
k2_2        = SxJ array of Kssmat in period t+1
euler1      = euler errors from first euler equation
euler2      = euler errors from second euler equation
------------------------------------------------------------------------
'''

k1 = np.array(list(np.zeros(J).reshape((1, J))) + list(Kssmat[:-1, :]))
k2 = Kssmat
k3 = np.array(list(Kssmat[1:, :]) + list(BQ.reshape(1, J)))
k1_2 = np.array(list(np.zeros(J).reshape((1, J))) + list(Kssmat))
k2_2 = np.array(list(Kssmat) + list(BQ.reshape(1, J)))
B = Bss * (1+rss)

K_eul3 = np.zeros((S, J))
K_eul3[:S-1, :] = Kssmat
K_eul3[-1, :] = BQ

euler1 = Euler1(wss, rss, e, Lssmat, k1, k2, k3, B)
euler2 = Euler2(wss, rss, e, Lssmat, k1_2, k2_2, B)
euler3 = Euler3(wss, rss, e, Lssmat, K_eul3, B)


# 2D Graph
plt.figure()
plt.plot(domain[1:], np.abs(euler1).max(1), label='Euler1')
plt.plot(domain, np.abs(euler2).max(1), label='Euler2')
plt.legend(loc=0)
plt.title('Euler Errors')
plt.xlabel(r'age cohort-$s$')
plt.savefig('OUTPUT/euler_errors1and2_SS_2D')

plt.figure()
plt.plot(domain[:J], np.abs(euler3.flatten()), label='Euler3')
plt.legend(loc=0)
plt.title('Euler Errors')
plt.xlabel(r'ability-$j$')
plt.savefig('OUTPUT/euler_errors_euler3_SS_2D')

# 3D Graph
X2, Y2 = np.meshgrid(domain[1:], Jgrid)

fig16 = plt.figure()
ax16 = fig16.gca(projection='3d')
ax16.plot_surface(X2, Y2, euler1.T, rstride=1, cstride=2, cmap=cmap2)
ax16.set_xlabel(r'Age Cohorts $S$')
ax16.set_ylabel(r'Ability Types $J$')
ax16.set_zlabel('Error Level')
ax16.set_title('Euler Errors')
plt.savefig('OUTPUT/euler_errors_euler1_SS_3D')

fig17 = plt.figure()
ax17 = fig17.gca(projection='3d')
ax17.plot_surface(X, Y, euler2.T, rstride=1, cstride=2, cmap=cmap2)
ax17.set_xlabel(r'Age Cohorts $S$')
ax17.set_ylabel(r'Ability Types $J$')
ax17.set_zlabel('Error Level')
ax17.set_title('Euler Errors')
plt.savefig('OUTPUT/euler_errors_euler2_SS_3D')

print '\tFinished.'

'''
------------------------------------------------------------------------
Save variables/values so they can be used in other modules
------------------------------------------------------------------------
'''

print 'Saving steady state variable values.'
var_names = ['S', 'beta', 'sigma', 'alpha', 'nu', 'A', 'delta', 'e', 'E',
             'J', 'Kss', 'Kssvec', 'Kssmat', 'Lss', 'Lssvec', 'Lssmat',
             'Yss', 'wss', 'rss', 'runtime', 'hours', 'minutes', 'omega',
             'seconds', 'eta', 'chi_n', 'chi_b', 'ltilde', 'ctilde', 'T',
             'g_n', 'g_y', 'omega_SS', 'TPImaxiter', 'TPImindist', 'BQ',
             'children', 'surv_rate', 'mort_rate', 'Bss', 'bin_weights',
             'bqtilde']
dictionary = {}
for key in var_names:
    dictionary[key] = globals()[key]
pickle.dump(dictionary, open("OUTPUT/ss_vars.pkl", "w"))
print '\tFinished.'