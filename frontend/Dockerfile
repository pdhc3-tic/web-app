#FROM node:20-alpine

#WORKDIR /app

#ENV NEXT_TELEMETRY_DISABLED=1

#COPY package.json package-lock.json ./
#RUN npm ci

#COPY . .

#ARG NEXT_PUBLIC_API_URL
#ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

#RUN npm run build

#ENV NODE_ENV=production

#EXPOSE 3000

#CMD ["npm", "run", "start"]

FROM node:20-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--webpack"]