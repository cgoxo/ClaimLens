// Loaded only when VITE_AUTH_MODE=firebase, so dev and tests never initialise Firebase.
import { initializeApp } from "firebase/app";
import { GoogleAuthProvider, getAuth, onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";

const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});
const auth = getAuth(app);

export const firebase = {
  onUser: (cb: (user: User | null) => void) => onAuthStateChanged(auth, cb),
  signIn: () => signInWithPopup(auth, new GoogleAuthProvider()),
  signOut: () => signOut(auth),
  token: async () => (auth.currentUser ? auth.currentUser.getIdToken() : null),
};
