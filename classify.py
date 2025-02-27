import os
import joblib
import pandas as pd
import tensorflow as tf

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from time import sleep

from dotenv import load_dotenv

load_dotenv()

dataset = os.getenv("DATASET_PATH")

with open(dataset, 'r', encoding='utf-8') as file:
    lines = file.readlines()

data = []
for line in lines:
    label, message = line.strip().split(' ', 1)
    data.append({"label": label, "message": message})

df = pd.DataFrame(data)

df['label'] = df['label'].map({'ham': 0, 'spam': 1})

X = df['message']
y = df['label']

vectorizer = TfidfVectorizer()
X_tfidf = vectorizer.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(X_tfidf, y, test_size=0.2, random_state=42)

model = tf.keras.models.Sequential([
    tf.keras.layers.Dense(128, activation='relu', input_shape=(X_train.shape[1],)),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dense(1, activation='sigmoid')
])

def train(mode):
    with open(dataset, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    data = []
    for line in lines:
        label, message = line.strip().split(' ', 1)
        data.append({"label": label, "message": message})

    df = pd.DataFrame(data)
    df['label'] = df['label'].map({'ham': 0, 'spam': 1})
    X = df['message']
    y = df['label']

    vectorizer = TfidfVectorizer()
    X_tfidf = vectorizer.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(X_tfidf, y, test_size=0.2, random_state=42)

    model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(128, activation='relu', input_shape=(X_train.shape[1],)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

    model.fit(X_train, y_train, epochs=25, batch_size=32, validation_data=(X_test, y_test))

    loss, accuracy = model.evaluate(X_test, y_test)
    print(f'Тестовая точность: {accuracy}\nLoss: {loss}')

    try:
        os.remove("classify.keras")
        os.remove("vectorizer.pkl")
    except:
        pass

    sleep(0.2) 

    model.save('classify.keras')
    joblib.dump(vectorizer, 'vectorizer.pkl') 

    print("Модель и vectorizer сохранены")

    if mode == "r":
        return accuracy


def classify_message(message):
    model = tf.keras.models.load_model('classify.keras')
    vectorizer = joblib.load('vectorizer.pkl')  

    message_tfidf = vectorizer.transform([message])   
    message_tfidf_dense = message_tfidf.toarray()

    prediction = model.predict(message_tfidf_dense)

    if prediction >= 0.5:
        return True
    else:
        return False
