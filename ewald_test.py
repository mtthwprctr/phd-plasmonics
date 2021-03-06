#! /usr/bin/python3

"""
Small script for testing Ewald's method on interactions via a 2D Green's function on a 2D lattice
"""

import numpy as np
import scipy as sp
from scipy import special  # used for hankel functions
from scipy import optimize
from matplotlib import pyplot as plt
from multiprocessing import Pool
import itertools

global ev
ev = (1.602*10**-19 * 2 * np.pi)/(6.626*10**-34 * 2.997*10**8)


class Lattice:
    """
    Quick class to set up a lattice defined by two lattice vectors a1, a2.
    """
    def __init__(self, a1, a2):
        R = np.array([[0, -1],[1, 0]])  # Rotation matrix for defining reciprocal lattice vectors
        self.a1 = a1
        self.a2 = a2
        self.b1 = 2*np.pi * np.dot(R, self.a2)/np.dot(self.a1, np.dot(R, self.a2))
        self.b2 = 2*np.pi * np.dot(R, self.a1)/np.dot(self.a2, np.dot(R, self.a1))

    def genBravais(self, number, origin):
        """
        Returns a list of Bravais lattice points. Origin is True or False depending on whether [0,0] point is required.
        """
        bravais = []
        neighbours = np.arange(-number, number + 1)
        for n, m in itertools.product(neighbours, repeat=2):
            if origin is False:
                if n != 0 or m != 0:  # to exclude origin
                    bravais.append(n*np.array(self.a1) + m*np.array(self.a2))
            else:
                    bravais.append(n*np.array(self.a1) + m*np.array(self.a2))
        return bravais

    def genReciprocal(self, number, origin):
        """
        Returns a list of reciprocal lattice points. Origin is True or False depending on whether [0,0] point is required.
        """
        reciprocal = []
        neighbours = np.arange(-number, number + 1)

        for n, m in itertools.product(neighbours, repeat=2):
            if origin is False:
                if n != 0 or m != 0:  # to exclude origin
                    reciprocal.append(n*np.array(self.b1) + m*np.array(self.b2))
            else:
                    reciprocal.append(n*np.array(self.b1) + m*np.array(self.b2))
        return reciprocal

    def getBravaisVectors(self):
        """
        Returns Bravais lattice vectors.
        """
        return [self.a1, self.a2]

    def getReciprocalVectors(self):
        """
        Returns reciprocal lattice vectors.
        """
        return [self.b1, self.b2]


class Interaction:
    """
    Defines interactions between particles via 2D Green's function.
    """
    def __init__(self, q, lattice, neighbours, position, origin):
        """
        args:
        - q: point in reciprocal space
        - lattice: set of lattice points
        - position: point in real space
        """
        self.q = q
        self.lattice = lattice
        self.bravais = lattice.genBravais(neighbours, origin)
        self.reciprocal = lattice.genReciprocal(neighbours, True)
        self.pos = position

    def monopolar_green(self, w, distance, lat_vec):
        """
        Usual Green's function term in 2D.
        """
        k = w*ev
        return 0.25j*sp.special.hankel1(0, k*np.linalg.norm(distance))*np.exp(1j*np.dot(self.q, lat_vec))

    def _monopolar_green(self, args):
        # wrapper for multiprocessing
        return self.monopolar_green(*args)

    def monopolarSum(self, w):
        """
        Calculates sums for monopolar Green's function over Bravais lattice.
        """
        # results = []
        # pool = Pool()  # multiprocessing speeds things up
        # values = [(w, np.array(self.pos - i), i) for i in self.bravais]
        # results.append(pool.map(self._monopolar_green, values))
        # pool.close()
        # return sum(results[0])

        _sum = 0
        for i in self.bravais:
            _sum += self.monopolar_green(w, np.array(self.pos - i), i)
        return _sum

    def green_dyadic(self, w, distance, lat_vec):
        """
        Dyadic Green's function term in 2D, for dipolar sources.
        """
        k = w*ev

        x = distance[0]
        y = distance[1]
        R = np.linalg.norm(distance)
        theta = np.angle(x + 1j*y)
        arg = k*R

        # xx_type = 0.25j * (k**2 *sp.special.hankel1(0,arg) - ((k**2*x**2)/(2*R**2))*(sp.special.hankel1(0, arg) - sp.special.hankel1(2, arg)) + (k*x**2/R**3) * sp.special.hankel1(1, arg) - (k/R)*sp.special.hankel1(1, arg))

        # xy_type = 0.25j * ((k**2*x*y)/(R**2))*sp.special.hankel1(2, arg)

        # yy_type = 0.25j * (k**2 * sp.special.hankel1(0,arg) - ((k**2*y**2)/(2*R**2))*(sp.special.hankel1(0, arg) - sp.special.hankel1(2, arg)) + (k*y**2/R**3) * sp.special.hankel1(1, arg) - (k/R)*sp.special.hankel1(1, arg))

        # xx_type = 0.25j * k**2 * (
        # (y**2/R**2) * sp.special.hankel1(0,arg) +
        # (x**2 - y**2)/(k*R**3) * sp.special.hankel1(1, arg)
        # )
        #
        # yy_type = 0.25j * k**2 * (
        # (x**2/R**2) * sp.special.hankel1(0,arg) -
        # (x**2 - y**2)/(k*R**3) * sp.special.hankel1(1, arg)
        # )
        #
        # xy_type = 0.25j * k**2 * x*y/R**2 * sp.special.hankel1(2,arg)

        a = 0.125j * sp.special.hankel1(0, arg)
        b = 0.125j * sp.special.hankel1(2, arg) * np.sin(2*theta)
        c = 0.125j * sp.special.hankel1(2, arg) * np.cos(2*theta)
        
        xx_type = a + c
        xy_type = b
        yy_type = a - c

        return np.array([xx_type, xy_type, yy_type])

    def _green_dyadic(self, args):
        # wrapper for multiprocessing
        return self.green_dyadic(*args)

    # def dyadicSum(self, w):
    #     """
    #     Calculates sums for dyadic Green's function over Bravais lattice.
    #     """
    #     results = []
    #     pool = Pool()
    #     values = [(w, np.array(self.pos - i), i) for i in self.bravais]
    #     results.append(pool.map(self._green_dyadic, values))
    #     pool.close()
    #     return sum(results[0])

    def dyadicSum(self, w):
        _sum = 0
        for i in self.bravais:
            _sum += self.green_dyadic(w, np.array(self.pos - i), i)*np.exp(1j*np.dot(self.q, i))
        return _sum

class Ewald:
    # This class could benefit from some cleaning up as a lot of the expressions are long and messy.
    """
    Contains all the terms required in Ewald's summation.
    """
    def __init__(self, ewald, j_max, q, lattice, neighbours, position, n, n_max=0):
        self.q = q
        self.lattice = lattice
        self.bravais = lattice.genBravais(neighbours, True)
        self.reciprocal = lattice.genReciprocal(neighbours, True)
        self.pos = position
        self.E = ewald
        self.j_max = j_max
        self.neighbours = neighbours
        self.n_max = n_max

    def ewaldG1(self, w):
        k = w*ev
        a1, a2 = self.lattice.getBravaisVectors()

        area = float(np.cross(a1, a2))
        _sum = 0
        for G_pos in self.reciprocal:
            _sum += (1./area) * (np.exp(1j*np.dot(self.q+G_pos, self.pos)) * np.exp((k**2 - np.linalg.norm(self.q+G_pos)**2)/(4*self.E**2)))/(np.linalg.norm(self.q+G_pos)**2 - k**2)
        return _sum

    def integralFunc(self, separation, w):
        k = w*ev
        _sum = 0
        for j in range(0, self.j_max+1):
            _sum += (1./np.math.factorial(j)) * (k/(2*self.E))**(2*j) * sp.special.expn(j+1, separation**2*self.E**2)

        return _sum

    def ewaldG2(self, w):
        _sum = 0
        for R_pos in self.bravais:
            distance = np.linalg.norm(self.pos - R_pos)
            _sum += (1./(4*np.pi)) * np.exp(1j * np.dot(self.q, R_pos)) * self.integralFunc(distance, w)


        return _sum

    def monopolarSum(self, w):
        return self.ewaldG1(w) + self.ewaldG2(w)

    def dyadicEwaldG1(self, w, _type):
        k = w*ev
        a1, a2 = self.lattice.getBravaisVectors()
        area = float(np.cross(a1, a2))
        _sum = 0
        if _type is "xx":
            for G_pos in self.reciprocal:
                beta = self.q + G_pos
                beta_norm = np.linalg.norm(beta)

                _sum += (k**2 + beta[0]**2) * (1./area) * (np.exp(1j*np.dot(beta, self.pos)) * np.exp((k**2 - beta_norm**2)/(4*self.E**2)))/(beta_norm**2 - k**2)
        elif _type is "xy":
            for G_pos in self.reciprocal:
                beta = self.q + G_pos
                beta_norm = np.linalg.norm(beta)

                _sum += (beta[0]*beta[1]) * (1./area) * (np.exp(1j*np.dot(beta, self.pos)) * np.exp((k**2 - beta_norm**2)/(4*self.E**2)))/(beta_norm**2 - k**2)
        elif _type is "yy":
            for G_pos in self.reciprocal:
                beta = self.q + G_pos
                beta_norm = np.linalg.norm(beta)
                _sum += (k**2 + beta[1]**2) * (1./area) * (np.exp(1j*np.dot(beta, self.pos)) * np.exp((k**2 - beta_norm**2)/(4*self.E**2)))/(beta_norm**2 - k**2)
        return _sum

    def dyadicEwaldG2(self, w, _type):
        k = w*ev
        _sum = 0
        if _type is "xx":
            for R_pos in self.bravais:
                rho = self.pos - R_pos
                rho_norm =  np.linalg.norm(rho)
                _sum += (np.exp(1j * np.dot(self.q, R_pos))) * (self.dyadicIntegralFunc(w, rho, _type) + (np.exp(-rho_norm**2*self.E**2)/rho_norm**2)*(((4*rho[0]**2)/rho_norm**2)*(rho_norm**2*self.E**2 + 1) - 2))

        elif _type is "xy":
            for R_pos in self.bravais:
                rho = self.pos - R_pos
                rho_norm =  np.linalg.norm(rho)
                _sum += np.exp(1j * np.dot(self.q, R_pos)) * (self.dyadicIntegralFunc(w, rho, _type) + (np.exp(-rho_norm**2*self.E**2) * (4*rho[0]*rho[1]/rho_norm**2)*(rho_norm**2*self.E**2 + 1)))

        elif _type is "yy":
            for R_pos in self.bravais:
                rho = self.pos - R_pos
                rho_norm =  np.linalg.norm(rho)
                _sum += (np.exp(1j * np.dot(self.q, R_pos))) * (self.dyadicIntegralFunc(w, rho, _type) + (np.exp(-rho_norm**2*self.E**2)/rho_norm**2)*(((4*rho[1]**2)/rho_norm**2)*(rho_norm**2*self.E**2 + 1) - 2))
        return _sum/(4*np.pi)

    def dyadicIntegralFunc(self, w, rho, _type):
        k = w*ev
        _sum = 0
        rho_norm = np.linalg.norm(rho)
        if _type is "xx":
            for j in range(1, self.j_max+1):
                _sum += ((1./np.math.factorial(j)) * (k/(2*self.E))**(2*j)) * (4*rho[0]**2*self.E**4*sp.special.expn(j-1, rho_norm**2*self.E**2) - 2*self.E**2*sp.special.expn(j, rho_norm**2*self.E**2))

        elif _type is "xy":
            for j in range(1, self.j_max+1):
                _sum += ((1./np.math.factorial(j)) * (k/(2*self.E))**(2*j)) * (4*rho[0]*rho[1]*self.E**4*sp.special.expn(j-1, rho_norm**2*self.E**2))

        elif _type is "yy":
            for j in range(1, self.j_max+1):
                _sum += ((1./np.math.factorial(j)) * (k/(2*self.E))**(2*j)) * (4*rho[1]**2*self.E**4*sp.special.expn(j-1, rho_norm**2*self.E**2) - 2*self.E**2*sp.special.expn(j, rho_norm**2*self.E**2))

        return _sum

    def dyadicSumEwald(self, w):
        k = w*ev
        xx_comp = (self.dyadicEwaldG1(w, "xx") + self.dyadicEwaldG2(w, "xx") + k**2*self.ewaldG2(w))
        xy_comp = (self.dyadicEwaldG1(w, "xy") + self.dyadicEwaldG2(w, "xy"))
        yy_comp = (self.dyadicEwaldG1(w, "yy") + self.dyadicEwaldG2(w, "yy") + k**2*self.ewaldG2(w))
        return [xx_comp, xy_comp, yy_comp]

    def t0(self, w):  # NB: only non zero for n != 0
        k = w*ev
        return (-1 - (1j/np.pi)*sp.special.expi(k**2/(4*self.E**2)))
   
    def memoize(f):  # speed up recurrence relation below by caching previous results
        cache = {}
        def decorated_function(*args):
            if args in cache:
                return cache[args]
            else:
                cache[args] = f(*args)
                return cache[args]
        return decorated_function 

    #@memoize
    def t1_lim(self, w, n):
        k = w*ev
        _sum = 0
        

        a1, a2 = self.lattice.getBravaisVectors()
        area = float(np.cross(a1, a2))
        
        for G_pos in self.reciprocal:
            beta = self.q + G_pos
            beta_norm = np.linalg.norm(beta)
            phi = np.arctan2(beta[1],beta[0])
            #phi = np.angle(beta[0] + 1j*beta[1])

            if n < 0:
                n = abs(n)

            _sum += (4/area)*(1j**(n+1)) * (1/(k**2-beta_norm**2)) * np.exp((k**2 - beta_norm**2)/(4*self.E**2)) * ((beta_norm/k)**n) * np.exp(-1j*n*phi)
            
        if n < 0:
            _sum = -np.conjugate(_sum)
        return _sum

    @memoize
    def t2_lim(self, w, n):
        k = w*ev
        _sum = 0

        for R_pos in self.lattice.genBravais(self.neighbours, False):  # sum excluding origin
            R_norm = np.linalg.norm(R_pos)
            
            alpha = np.arctan2(R_pos[1],R_pos[0])
            #alpha = np.angle(R_pos[0] + 1j*R_pos[1])
            if n == 0:
                _sum += (-2j/np.pi)*np.exp(1j*np.dot(self.q, R_pos))*self.t2_I_0(R_norm, w)
            elif n > 0:
                _sum += -(2**(n+1))*(1j/np.pi) * np.exp(1j*np.dot(self.q, R_pos)) * np.exp(-1j*n*alpha) * ((R_norm/k)**n) * self.t2_I_n(R_norm, w, n)
            elif n < 0:
                m = abs(n)
                _sum +=-(2**(m+1))*(1j/np.pi) * np.exp(1j*np.dot(self.q, R_pos)) * np.exp(-1j*m*alpha) * ((R_norm/k)**m) * self.t2_I_n(R_norm, w, m)

        if n < 0:
            _sum = -np.conjugate(_sum)
        return _sum
        
        
    def t1(self, w, n_max):
        k = w*ev
        _sum = 0
        a1, a2 = self.lattice.getBravaisVectors()
        area = float(np.cross(a1, a2))
        
        for G_pos in self.reciprocal:
            beta = self.q + G_pos
            beta_norm = np.linalg.norm(beta)
            phi = np.angle(beta[0] + 1j*beta[1])

            _sum += (4j/area) * 1/(k**2-beta_norm**2) * np.exp((k**2 - beta_norm**2)/(4*self.E**2))
        
        if n_max != 0:
            for n in range(1, self.n_max):
                for G_pos in self.reciprocal:
                    beta = self.q + G_pos
                    beta_norm = np.linalg.norm(beta)
                    phi = np.angle(beta[0] + 1j*beta[1])
                    
                    _sum += (4j/area) * 1/(k**2-beta_norm**2) * np.exp((k**2 - beta_norm**2)/(4*self.E**2)) * (((1j*beta_norm)/(k*np.exp(1j*phi)))**n + ((1j*beta_norm)/(k*np.exp(1j*phi)))**-n)
                #print("t1: " + str(n))

        return _sum


    def t2(self, w, n_max):
        k = w*ev

        _sum = 0
        for R_pos in self.lattice.genBravais(self.neighbours, False):  # sum excluding origin
            R_norm = np.linalg.norm(R_pos)
            alpha = np.angle(R_pos[0] + 1j*R_pos[1])

            _sum += (-1j/np.pi)*np.exp(1j*np.dot(self.q, R_pos))*self.t2_I_0(R_norm, w)

        if n_max != 0:
            for n in range(1, self.n_max):
                for R_pos in self.lattice.genBravais(self.neighbours, False):  # sum excluding origin
                    R_norm = np.linalg.norm(R_pos)
                    alpha = np.angle(R_pos[0] + 1j*R_pos[1])

                    _sum -= 2**(n+1) * (1j/np.pi) * (R_norm/k)**n * (2*np.cos(np.dot(self.q, R_pos)-n*alpha)) * self.t2_I_n(R_norm, w, n)
                #print("t2: " + str(n))
        return _sum

    

    @memoize    
    def t2_I_n(self, dist, w, n):  # recurrence relation
        k = w*ev
        if n == 1:
            return self.t2_I_1(dist, w)
        elif n == 2:  # I_2
            return +((self.E**2)/(2*dist**2)) * np.exp(k**2/(4*self.E**2) - dist**2*self.E**2) + (self.t2_I_1(dist, w)/dist**2) - (k**2/(4*dist**2))*self.t2_I_0(dist, w)
        else:
            return +((self.E**(2*(n-1)))/(2*(n-1)*dist**2))*np.exp(k**2/(4*self.E**2) - dist**2*self.E**2) + (self.t2_I_n(dist, w, n-1)/dist**2) - (k**2/(4*dist**2))*self.t2_I_n(dist, w, n-2)

    def t2_I_0(self, dist, w):  # integral I_0 of recurrence relat0.5*self.E**2*self.t2IntegralFunc(dist, w, 0)ion
        return 0.5*self.t2IntegralFunc(dist, w, 1)

    def t2_I_1(self, dist, w):  # integral I_1 of recurrence relation
        return 0.5*self.E**2*self.t2IntegralFunc(dist, w, 0)

    def t2IntegralFunc(self, dist, w, j_factor):
        k = w*ev
        _sum = 0
        for j in range(0, self.j_max+1):
            _sum = (1/(np.math.factorial(j))) * ((k/(2*self.E))**(2*j)) * sp.special.expn(j+j_factor, dist**2*self.E**2)
        return _sum

    def reducedLatticeSum(self, w):
        k = w*ev
        _sum = -0.25j*(self.t0(w) + self.t1_lim(w, self.n) + self.t2_lim(w, self.n))
        
        return _sum

    def reducedDyadicSum(self, w):
        k = w*ev

        h_0 = (self.t0(w) + self.t1_lim(w, 0) + self.t2_lim(w, 0))
        #h_neg2 = (self.t1_lim(w, -2) + self.t2_lim(w, -2))  # H_2
        h_pos2 = (self.t1_lim(w, 2) + self.t2_lim(w, 2))  # H_(-2)
        h_neg2 = -np.conjugate(h_pos2)
        xx = -(1j/8)*h_0 - (1j/16)*(h_neg2+h_pos2)
        xy = -(1/16)*(h_neg2-h_pos2)
        yy = -(1j/8)*h_0 + (1j/16)*(h_neg2+h_pos2)
        return [xx, xy, yy]

def testLatticeSum(vector_1, vector_2, neighbour_range, q, w, pos):
    """
    Plots graphs of monopolar lattice sums. Returns graph of non-converging original method and converging sums with Ewald's method.
    """
    results = []
    ewald_results = []
    loop_range = range(1, neighbour_range+1)
    lattice = Lattice(vector_1, vector_2)

    print("monopolar sum")
    fig, ax = plt.subplots(2,2)

    if np.linalg.norm(np.array(pos)) == 0:  # if you are the origin, then exclude it from the sum
        fig.suptitle("Scalar sum excluding origin")
        print("Sum excluding origin")
        for i in loop_range:
            results.append(Interaction(q, lattice, i, pos, False).monopolarSum(w))
            print(i**2-1)
            ewald_results.append(Ewald(2*np.pi/(a), 5, q, lattice, i, pos, 0).reducedLatticeSum(w))
        print("done")
    else:
        fig.suptitle("Scalar sum including origin".format(pos))
        print("Sum including origin")
        for i in loop_range:
            results.append(Interaction(q, lattice, i, pos, True).monopolarSum(w))
            print(i**2-1)
            ewald_results.append(Ewald(2*np.pi/(a), 5, q, lattice, i, pos, 0).monopolarSum(w))
        print("done")

    ax[0][0].set_title("Non-Ewald, Re")
    ax[1][0].set_title("Non-Ewald, Im")
    ax[0][1].set_title("Ewald, Re")
    ax[1][1].set_title("Ewald, Im")

    ax[0][0].plot([i**2-1 for i in loop_range], [i.real for i in results],'r')
    ax[1][0].plot([i**2-1 for i in loop_range], [i.imag for i in results],'r--')
    print(sum(results)/len(results))

    ax[0][1].plot([i**2-1 for i in loop_range], [i.real for i in ewald_results],'g')
    ax[1][1].plot([i**2-1 for i in loop_range], [i.imag for i in ewald_results],'g--')
    print(ewald_results[neighbour_range-1])
    fig.text(0.5, 0.04, 'Number of terms in sum', ha='center')

    plt.show()


def testDyadicSum(vector_1, vector_2, neighbour_range, q, w, pos=[0, 0]):
    """
    Plots graphs of dipolar lattice sums. Returns graph of non-converging original method and converging sums with Ewald's method.
    """
    results = []
    ewald_results = []
    loop_range = range(1, neighbour_range+1)
    ewald_range = range(1,22)
    lattice = Lattice(vector_1, vector_2)

    #print("dyadic sum")

    fig, ax = plt.subplots(3,4)

    if np.linalg.norm(np.array(pos)) == 0:  # if you are the origin, then exclude it from the sum
        #fig.suptitle("Dyadic sums excluding origin")

        #print("Sum excluding origin")
        for i in loop_range:
            results.append(Interaction(q, lattice, i, pos, False).dyadicSum(wp))
            print(i)
        for i in ewald_range:
            ewald_results.append(Ewald(2*np.pi/a, 5, q, lattice, i, pos, 0).reducedDyadicSum(wp))
        #print("done")
    else:
        #fig.suptitle("Dyadic sums including origin")

        #print("Sum including origin")
        for i in loop_range:
            results.append(Interaction(q, lattice, i, pos, True).dyadicSum(wp))
            ewald_results.append(Ewald(2*np.pi/a, 20, q, lattice, i, pos, 0).monopolarSum(wp))
            print(i**2-1)
        #print("done")

    avg = (sum(results)/len(results))

    ax[0][0].set_title("Non-Ewald, Re")
    ax[0][1].set_title("Non-Ewald, Im")
    ax[0][2].set_title("Ewald, Re")
    ax[0][3].set_title("Ewald, Im")

    ax[0][0].set_ylabel("$\partial^2/\partial x^2$ sum")
    ax[1][0].set_ylabel("$\partial^2/\partial x \partial y$ sum")
    ax[2][0].set_ylabel("$\partial^2/\partial y^2$ sum")
    for j in range(3):
        ax[j][0].plot([i**2-1 for i in loop_range], [i[j].real for i in results], 'r')
        ax[j][1].plot([i**2-1 for i in loop_range], [i[j].imag for i in results], 'r--')
        ax[j][2].plot([i**2-1 for i in ewald_range], [i[j].real for i in ewald_results], 'g')
        ax[j][3].plot([i**2-1 for i in ewald_range], [i[j].imag for i in ewald_results], 'g--')
    fig.text(0.5, 0.04, 'Number of terms in sum', ha='center')
    #print("d_xx, d_xy, d_yy averages: {}".format(sum(results)/len(results)))
    #print("convergent ewald result: {}".format(ewald_results[9]))
    #print("finished for q={}".format(q))


    fig, ax = plt.subplots(3,2)

    ax[0][0].plot([i**2-1 for i in ewald_range], [np.abs((i[0].real - avg[0].real)/avg[0].real)*100 for i in ewald_results], 'b')
    ax[0][1].plot([i**2-1 for i in ewald_range], [np.abs((i[0].imag - avg[0].imag)/avg[0].imag)*100 for i in ewald_results], 'b--')

    ax[1][0].plot([i**2-1 for i in ewald_range], [np.abs((i[1].real - avg[1].real)/avg[1].real)*100 for i in ewald_results], 'c')
    ax[1][1].plot([i**2-1 for i in ewald_range], [np.abs((i[1].imag - avg[1].imag)/avg[1].imag)*100 for i in ewald_results], 'c--')

    ax[2][0].plot([i**2-1 for i in ewald_range], [np.abs((i[2].real - avg[2].real)/avg[2].real)*100 for i in ewald_results], 'y')
    ax[2][1].plot([i**2-1 for i in ewald_range], [np.abs((i[2].imag - avg[2].imag)/avg[2].imag)*100 for i in ewald_results], 'y--')

    errors = []
    labels = ["xx", "xy", "yy"]
    for i in range(3):
        errors.append(str("{} Re error: {}%, Im error: {}".format(labels[i], round((np.abs((ewald_results[-1][i].real - avg[i].real)/avg[i].real)*100), 2), round((np.abs((ewald_results[-1][i].imag - avg[i].imag)/avg[i].imag)*100), 2))))

    print(errors)

    #plt.show()
    fig, ax = plt.subplots(1)
    plt.scatter(q[0],q[1])
    plt.plot([-np.pi/a, -np.pi/a, np.pi/a, np.pi/a, -np.pi/a],[-np.pi/a, +np.pi/a, np.pi/a, -np.pi/a, -np.pi/a], c="k")
    plt.plot([0, np.pi/a, np.pi/a, 0],[0, np.pi/a, 0, 0], c='r')
    fig.text(0,0, "")
    plt.show()


if __name__ == '__main__':
    ev = (1.602*10**-19 * 2 * np.pi)/(6.626*10**-34 * 2.997*10**8)
    a = 15*10**-9
    radius = 5*10**-9
    wp = 3.5
    loss = 0.01
    a1 = np.array([0, a])
    a2 = np.array([a, 0])
    pos = np.array([0, 0])
    q = np.array([0.*np.pi/a, 0.*np.pi/a])
    #83775804.0957278

    #testComponents(a1, a2, 20, q, wp, pos, 18)
    testDyadicSum(a1, a2, 100, q, wp, pos)
    #testLatticeSum(a1, a2, 20, q, wp, pos)
