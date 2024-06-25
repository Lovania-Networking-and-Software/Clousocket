import numpy as np
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KernelDensity, KNeighborsTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class ReqClassifier:
    def __init__(self):
        self.x = []
        self.y = []
        self.x_without_outlier = []
        self.test_x = []
        self.test_y = []

        self.prep_data()
        self.x = np.array(self.x)
        self.test_x = np.array(self.test_x)
        self.x_without_outlier = np.array(self.x_without_outlier)

        self.kd = KernelDensity(kernel='epanechnikov', bandwidth="silverman", algorithm="ball_tree")
        self.ny = Nystroem(n_components=60)
        self.knt = KNeighborsTransformer(n_neighbors=20, mode='distance')
        self.ss = StandardScaler()

        self.pp = make_pipeline(self.ss, self.knt, self.ny)

        self.x = self.pp.fit_transform(self.x)
        self.kd.fit(self.x)

        self.x = self.x * self.kd.score_samples(self.x).reshape(-1, 1)

        self.test_x = self.pp.transform(self.test_x)
        self.test_x = self.test_x * self.kd.score_samples(self.test_x).reshape(-1, 1)

        self.cl = SGDClassifier(random_state=0)

        param_g = {
            "loss"   : ['hinge', 'log_loss', 'modified_huber', 'squared_hinge', 'perceptron', 'squared_error', 'huber',
                        'epsilon_insensitive', 'squared_epsilon_insensitive'],
            "penalty": ['l2', 'l1', 'elasticnet'],
            "tol"    : [0.01, 0.001, 0.0001, 0.00001],
            "alpha"  : [0.01, 0.001, 0.0001, 0.00001],
        }
        self.cl = GridSearchCV(self.cl, param_g, cv=5)

    def prep_data(self):
        for command_cn in range(0, 3):
            for risk in range(0, 4):
                self.x.append([risk, command_cn])
                self.test_x.append([risk, command_cn])
                self.x_without_outlier.append([risk, command_cn])
                self.y.append(0)
                self.test_y.append(0)
        for command_cn in range(3, 8):
            for risk in range(0, 11):
                self.test_x.append([risk, command_cn])
                if risk < 3:
                    self.test_y.append(0)
                    continue
                elif risk > 9:
                    self.test_y.append(1)
                    continue
                self.x.append([risk, command_cn])
                if command_cn == 3 and risk >= 7:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 4 and risk >= 6:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 5 and risk >= 5:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 6 and risk >= 4:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 7 and risk >= 3:
                    self.y.append(1)
                    self.test_y.append(1)
                else:
                    self.x_without_outlier.append([risk, command_cn])
                    self.y.append(0)
                    self.test_y.append(0)
        for command_cn in range(8, 11):
            for risk in range(0, 11):
                self.test_x.append([risk, command_cn])
                self.x.append([risk, command_cn])
                if command_cn == 8 and risk >= 3:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 9 and risk >= 2:
                    self.y.append(1)
                    self.test_y.append(1)
                elif command_cn == 10 and risk >= 2:
                    self.y.append(1)
                    self.test_y.append(1)
                else:
                    self.x_without_outlier.append([risk, command_cn])
                    self.y.append(0)
                    self.test_y.append(0)

    def fit(self):
        self.cl.fit(self.x, self.y)

    def predict(self, risk, command_cn):
        x = self.pp.transform([[risk, command_cn]])
        x = x * self.kd.score(x)
        return self.cl.predict(x)[0]


if __name__ == '__main__':
    a = ReqClassifier()
    a.fit()
    res = a.cl.score(a.test_x, a.test_y)
    print(res)
    y_pred_rf = a.cl.predict(a.test_x)
    f1_rf = f1_score(a.test_y, y_pred_rf)
    print(f1_rf)
    if not res == 1.0:
        for i, d in enumerate(a.test_x):
            y = a.cl.predict(np.array([d]))[0]
            if y == a.test_y[i]:
                continue
            else:
                print(i)
