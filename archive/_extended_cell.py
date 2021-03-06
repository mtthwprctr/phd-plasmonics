#! python3

"""
Simulating Green's functions for electromagnetic interactions in an array of
plasmonic nanoparticles.
"""

import numpy as np
import scipy as sp
from scipy import special  # used for hankel functions
from scipy import optimize
from matplotlib import pyplot as plt
from multiprocessing import Pool
import itertools


class Particle:
    """
    Particle class.

    Each particle has a position, radius, plasma frequency and loss.
    """
    def __init__(self, x_pos, y_pos, radius, wp, loss):
        self.R = np.array([x_pos, y_pos])
        self.radius = radius
        self.plasma = wp
        self.loss = loss


def honeycomb_reciprocal_space(spacing, resolution):
    """
    Create set of (x,y) coordinates for path in reciprocal space.

    From K to Gamma to M.
    """
    b = spacing * 3
    K_Gamma_x = np.linspace((4*np.pi)/(3*b), 0, resolution/2, endpoint=False)
    K_Gamma_y = np.zeros(int(resolution/2))

    Gamma_M_x = np.zeros(int(resolution/2))
    Gamma_M_y = np.linspace(0, (2*np.pi)/(np.sqrt(3)*b), resolution/2, endpoint=True)

    q_x = np.concatenate((K_Gamma_x, Gamma_M_x))
    q_y = np.concatenate((K_Gamma_y, Gamma_M_y))

    return np.array(list(zip(q_x, q_y)))


def green(k, distance):
    """
    Green's function interaction.

    Calculate the Green's function tensor between particles which are separated
    by a vector distance at a frequency k. For a 2D Green's function, the
    interactions are modelled with Hankel function.s

    Returns a matrix of the form [[G_xx, G_xy],[G_xy, G_yy]]
    """
    x = distance[0]
    y = distance[1]
    R = np.linalg.norm(distance)
    arg = k*R

    xx_type = 0.25j * k**2 * (
    (y**2/R**2) * sp.special.hankel1(0,arg) +
    (x**2 - y**2)/(k*R**3) * sp.special.hankel1(1, arg)
    )

    yy_type = 0.25j * k**2 * (
    (x**2/R**2) * sp.special.hankel1(0,arg) -
    (x**2 - y**2)/(k*R**3) * sp.special.hankel1(1, arg)
    )

    xy_type = 0.25j * k**2 * x*y/R**2 * sp.special.hankel1(2,arg)

    return np.array([[xx_type, xy_type], [xy_type, yy_type]])


def honeycomb(spacing, radius, wp, loss):
    """
    Honeycomb lattice.

    Create a honeycomb lattice with specific lattice spacing. Also define
    radii, plasma frequency and loss of particles in the lattice.
    """
    particle_coords = []

    particle_coords.append(Particle(spacing, 0, radius, wp, loss).R)
    particle_coords.append(Particle(spacing*0.5, -spacing*np.sqrt(3)/2, radius, wp, loss).R)
    particle_coords.append(Particle(-spacing*0.5, -spacing*np.sqrt(3)/2, radius, wp, loss).R)
    particle_coords.append(Particle(-spacing, 0, radius, wp, loss).R)
    particle_coords.append(Particle(-spacing*0.5, spacing*np.sqrt(3)/2, radius, wp, loss).R)
    particle_coords.append(Particle(spacing*0.5, spacing*np.sqrt(3)/2, radius, wp, loss).R)

    return np.array(particle_coords)


def square(spacing, radius, wp, loss):
    particle_coords = []

    particle_coords.append(Particle(0,0, radius, wp, loss).R)

    return np.array(particle_coords)


def square_interactions(intracell, intercell, w, q):
    H = np.zeros((2, 2), dtype=np.complex_)
    k = w*ev

    H = sum([green(k, inter) * np.exp(-1j * np.dot(q, inter)) for inter in intercell])
    return H


def square_tosolve(w, intracell, intercell, q):
    w = w[0] + 1j*w[1]
    H = square_interactions(intracell, intercell, w, q)
    H = H - np.identity(2)* polar(w, wp, g, r)
    return [np.linalg.det(H).real, np.linalg.det(H).imag]


def wrap_square_tosolve(args):
    return square_tosolve(*args)


def interactions(intracell, intercell, w, q):
    """
    Interaction matrix.

    Find the matrix of interactions for a 6 site unit cell system. Interactions
    are both between particle in the same cell (INTRAcell) and between
    particles in different cells (INTERcell). Calculated at a particular
    frequency omega (w) and Bloch wavenumber (q).
    """
    H = np.zeros((12, 12), dtype=np.complex_)

    k = w*ev

    # We only need to fill 'top right' diagonal of the matrix since 'opposite
    # direction' interactions are given by the Hermitian conjugate.

    indices = np.arange(len(intracell))
    for n, m in itertools.combinations(indices, 2):
        H[2*n:2*n+2, 2*m:2*m+2] = sum([green(k, -intracell[n] + intracell[m] + inter) * np.exp(1j * np.dot(q, -intracell[n] + intracell[m] + inter)) for inter in intercell])
        H[2*m:2*m+2, 2*n:2*n+2] = sum([green(k, -(-intracell[n] + intracell[m] + inter)) * np.exp(1j * np.dot(q, -(-intracell[n] + intracell[m] +  inter))) for inter in intercell])

    #H = H + np.conjugate(H).T  # the matrix is symmetrical about the diagonal (check this)


    # Create the diagonal by considering interactions between same particle
    # sites but in different cells. Need to make sure to ignore the (0,0)
    # element in intercell to prevent issues with the Green's function as we
    # have no 'self interaction'.
    for n in np.arange(len(intracell)):
        to_sum = []
        for inter in intercell:
            if np.linalg.norm(inter) != 0:  # ignore (0,0) position
                to_sum.append(green(k, inter) * np.exp(1j * np.dot(q, inter)))

        H[2*n:2*n+2, 2*n:2*n+2] = sum(to_sum)
    return H


def polar(w, wp, loss, radius):
    """Polarisability function.

    Dynamic polarisability for infinite cylinder.
    """
    k = w*ev
    eps = 1 - (wp**2)/(w**2 + 1j*loss*w)
    static = 2 * np.pi * radius**2 * ((eps-1)/(eps+1))
    return 1/(static/(1 - 1j * (k**2/8) * static))


def honeycomb_supercell(a, cell, t1, t2, max):
    """
    Create a repeated symmetrical list of points for the honeycomb lattice
    supercell structure.

    Returns a list of supercell positions (points) and particle positions
    (particles).
    """
    pos = cell
    points = []
    particles = []

    # for n in np.arange(-max, max+1):
    #     for m in np.arange(-max, max+1):
    #         points.append(n*t1+m*t2)
    #
    for n in np.arange(-max, max+1):
        if n < 0:
            for m in np.arange(-n-max, max+1):
                points.append(n*t1+m*t2)
        elif n > 0:
            for m in np.arange(-max, max-n+1):
                points.append(n*t1+m*t2)
        elif n == 0:
            for m in np.arange(-max, max+1):
                points.append(n*t1+m*t2)

    for p in points:
        for g in pos:
            particles.append(p + g)

    return points


def square_supercell(a, cell, t1, t2, max):
    particles = []
    for n in np.arange(-max, max+1):
        for m in np.arange(-max, max+1):
            if n != 0 or m != 0:
                particles.append(n*t1 + m*t2)

    return particles


def square_reciprocal(spacing, resolution):
    """Create set of (x,y) coordinates for path in reciprocal space.

    From Gamma to X to M to Gamma.
    """
    Gamma_X_x = np.linspace(0, np.pi/spacing, resolution/3, endpoint=False)
    Gamma_X_y = np.zeros(int(resolution/3))

    X_M_x = np.ones(int(resolution/3))*np.pi/spacing
    X_M_y = np.linspace(0, np.pi/spacing, resolution/3, endpoint=False)

    M_Gamma_x = np.linspace(np.pi/spacing, 0, resolution/3, endpoint=True)
    M_Gamma_y = np.linspace(np.pi/spacing, 0, resolution/3, endpoint=True)

    q_x = np.concatenate((Gamma_X_x, X_M_x, M_Gamma_x))
    q_y = np.concatenate((Gamma_X_y, X_M_y, M_Gamma_y))

    return np.array(list(zip(q_x, q_y)))


def plot_interactions(intracell, intercell):
    """
    Check if interactions between supercells are working properly. Also makes
    nice pictures.
    """
    i = 1
    to_plot = []
    for n in np.arange(len(intracell)):
        for m in np.arange(len(intracell)):
            for inter in intercell:
                point = intracell[m] + inter
                to_plot.append([[intracell[n][0], point[0]], [intracell[n][1], point[1]]])
        i += 1

    for i in to_plot:  # plot interactions
        plt.plot(i[0], i[1], zorder=0, alpha=0.1, c='r')
    for i in intercell:  # plot particle locations
        plt.scatter(i[0], i[1], c='k', zorder=1, alpha=0.1)
    plt.show()


def extinction(w, q, intracell, intercell):
    w_plasma = wp
    loss = g
    radius = r
    k = w*ev
    print(w)
    H_matrix = interactions(intracell, intercell, w, q)
    for i in range(len(H_matrix[0])):
        H_matrix[i][i] = H_matrix[i][i] - polar(w, w_plasma, loss, radius)

    return 4*np.pi*k*(sum(1/sp.linalg.eigvals(H_matrix)).imag)


def extinction_wrap(args):
    return extinction(*args)


def calculate_extinction(wrange, qrange, intracell, intercell):
    results = []
    wq_vals = [(w, q, intracell, intercell) for w in wrange for q in qrange]
    pool = Pool(16)

    results.append(pool.map(extinction_wrap, wq_vals))
    return results


def fixed_q_extinction(wrange, q, intracell, intercell):
    results = []
    wq_vals = [(w, q, intracell, intercell) for w in wrange]
    pool = Pool(16)

    results.append(pool.map(extinction_wrap, wq_vals))
    return results


def extinction_cross_section(wrange, q, intracell, intercell):
    results = fixed_q_extinction(wrange,q, intracell, intercell)
    fig, ax = plt.subplots()
    ax.plot(wrange, results[0])
    ax.plot([wp/np.sqrt(2), wp/np.sqrt(2)], [min(results[0]), max(results[0])], 'r--')
    ax.set_xlabel("Frequency $\omega$ (eV)")
    ax.set_ylabel("Extinction (a.u.)")
    ax.set_yticks([0])
    plt.show()


def dispersion_relation(q, intracell, intercell, resolution, wmin, wmax):
    matches = []
    print(q)
    for w in [wp/np.sqrt(2) +0.2, wp/np.sqrt(2)-0.2]:
        matches.append(sp.optimize.root(square_tosolve, ([w, 0.]), args = (intracell, intercell, q)).x)

    return matches

def disp_relation_wrap(args):
    return dispersion_relation(*args)

if __name__ == "__main__":
    a = 15.*10**-9  # lattice spacing
    r = 5.*10**-9  # particle radius
    wp = 6.18  # plasma frequency
    g = 0.01  # losses
    scaling = 1.
    ev = (1.602*10**-19 * 2 * np.pi)/(6.626*10**-34 * 2.997*10**8)  # k-> w conversion
    c = 2.997*10**8  # speed of light

    # trans_1 = np.array([scaling*3*a, 0])  # 1st Bravais lattice vector
    # trans_2 = np.array([scaling*3*a/2, scaling*np.sqrt(3)*3*a/2])  # 2nd Bravais lattice vector
    # intracell = honeycomb(a, r, wp, g)
    # intercell = honeycomb_supercell(a, intracell, trans_1, trans_2, 1)

    resolution = 90

    trans_1 = np.array([a, 0])
    trans_2 = np.array([0, a])
    intracell = square(a, r, wp, g)
    intercell = square_supercell(a, intracell, trans_1, trans_2, 2)
    wmin = 3.25
    wmax = 5.25
    qrange = square_reciprocal(a, resolution)

    #plot_interactions(intracell, intercell)

    # wmin = wp/np.sqrt(2) - 1
    # wmax = wp/np.sqrt(2) + 1
    # wmin = 4
    # wmax = 4.75
    #
    wrange = np.linspace(wmin, wmax, resolution, endpoint=True)
    # qrange = honeycomb_reciprocal_space(a, resolution)
    #
    light_line = [(np.linalg.norm(qval)/ev) for q, qval in enumerate(qrange)]
    plt.plot(light_line, zorder=1)
    raw_results = calculate_extinction(wrange, qrange, intracell, intercell)
    reshaped_results = np.array(raw_results).reshape((resolution, resolution))
    plt.imshow(reshaped_results, origin='lower', extent=[0, resolution-1, wmin, wmax], aspect='auto', cmap='viridis', zorder=0)
    plt.show()

####

    # res = []
    # q = qrange[90]
    # freq_range = [(w_re+1j*w_im, intracell, intercell, q) for w_re in wrange for w_im in np.linspace(-0.1, 0.1, resolution, endpoint=True)]
    # pool = Pool()
    # res.append(pool.map(wrap_square_tosolve, freq_range))
    # print(np.amin(res))
    # plt.imshow(np.array(res[0]).reshape((resolution, resolution)))
    # plt.show()

    # q = qrange[50]
    # k = wrange[50]*ev
    # H = [green(k, inter) * np.exp(-1j * np.dot(q, inter)) for inter in intercell]
    #
    # print(H[0])
    # print(H[1])
    # print(H[0] + H[1])
    # print(sum([H[0], H[1]]))

####

    # fig, ax = plt.subplots(2)
    # ax[0].set_title("spacing=15nm, radius=5nm, wp=6.18eV, loss=0.01eV. 2499 neighbours")
    # ax[0].set_ylabel("Re[$\omega (eV)]$")
    # ax[1].set_ylabel("Im[$\omega (eV)]$")
    # ax[0].set_xticklabels([])
    # ax[1].set_xticklabels([])
    # ax[0].set_ylim(3, 5.5)
    # ax[1].set_ylim(-0.5,0.5)
    # ax[0].set_xlim(0, resolution-1)
    # ax[1].set_xlim(0, resolution-1)
    #
    # ax[0].text(0,0, "$\Gamma$")
    # res = []
    # qvals = [(q, intracell, intercell, resolution, wmin, wmax) for q in qrange]
    # pool = Pool()
    # res.append(pool.map(disp_relation_wrap, qvals))
    #
    #
    # light_line = [(np.linalg.norm(qval)/ev) for q, qval in enumerate(qrange)]
    # ax[0].plot(light_line, zorder=0)
    #
    # for j in [0, 1]:
    #     ax[0].scatter(np.arange(resolution), [i[j][0] for i in res[0]], s=1, c='r')
    #     ax[1].scatter(np.arange(resolution), [i[j][1] for i in res[0]], s=1, c='b')
    #
    # ax[0].plot([resolution/3, resolution/3], [wmin-2, wmax+2], lw=1, c='k', alpha = 0.2)
    # ax[0].plot([2*resolution/3, 2*resolution/3], [wmin-2, wmax+2], lw=1, c='k', alpha = 0.2)
    #
    # ax[1].plot([resolution/3, resolution/3], [-1, 1], lw=1, c='k', alpha = 0.2)
    # ax[1].plot([2*resolution/3, 2*resolution/3], [-1, 1], lw=1, c='k', alpha = 0.2)
    #
    # ax[0].plot([0, resolution], [wp/np.sqrt(2), wp/np.sqrt(2)], lw=1, c='g')
    # ax[1].plot([0, resolution], [0, 0], lw=1, c='k')
    #
    # plt.show()
    #
    # print(res[0])
